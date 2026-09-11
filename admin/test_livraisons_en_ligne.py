"""Livraisons clients en ligne : les fichiers PHP déposés chez OVH.

python3 -m unittest discover -s admin -p 'test_*.py'

Le serveur intégré de PHP remplace Apache : il fait tourner le vrai code, mais
ignore .htaccess. Un routeur rejoue donc les deux règles qui comptent — la
jolie adresse /livraison/<id>/ et le refus de prives/ — pour que les chemins
éprouvés ici soient ceux du serveur. Les règles Apache elles-mêmes se vérifient
avec un vrai Apache, pas ici.
"""
import hashlib
import http.cookiejar
import io
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / 'admin-web' / 'livraison'
CLE = 'cle-d-essai-123'

ROUTEUR = """<?php
$u = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$base = __DIR__ . '/www';
if (preg_match('#^/livraison/[a-f0-9]{32}/prives#', $u)) { http_response_code(403); return true; }
if (preg_match('#^/livraison/([a-f0-9]{32})/?$#', $u, $m)) {
    $_GET['l'] = $m[1];
    $_SERVER['SCRIPT_NAME'] = '/livraison/index.php';
    require $base . '/livraison/index.php';
    return true;
}
if (preg_match('#^/livraison/(index|fichier|api)\\.php$#', $u, $m)) {
    $_SERVER['SCRIPT_NAME'] = '/livraison/' . $m[1] . '.php';
    require $base . '/livraison/' . $m[1] . '.php';
    return true;
}
return false;
"""


def php_absent():
    return shutil.which('php') is None


def port_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def empreinte(clair, tours=210000):
    sel = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac('sha256', clair.encode('utf-8'), sel, tours).hex()
    return 'pbkdf2$sha256$%d$%s$%s' % (tours, sel.hex(), h)


def jpeg(taille=(2400, 1600), couleur='#3377aa'):
    out = io.BytesIO()
    Image.new('RGB', taille, couleur).save(out, 'JPEG', quality=88)
    return out.getvalue()


def multipart(champs, fichiers):
    """champs : {nom: texte} · fichiers : [(nom, fichier, type, octets)]"""
    limite = '----sbt' + secrets.token_hex(8)
    corps = b''
    for nom, valeur in champs.items():
        corps += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                  % (limite, nom, valeur)).encode('utf-8')
    for nom, fichier, type_, octets in fichiers:
        corps += ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                  'Content-Type: %s\r\n\r\n' % (limite, nom, fichier, type_)).encode('utf-8')
        corps += octets + b'\r\n'
    corps += ('--%s--\r\n' % limite).encode('utf-8')
    return 'multipart/form-data; boundary=' + limite, corps


@unittest.skipIf(php_absent(), 'php absent de cette machine')
class EnLigneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        base = Path(cls.temp.name)
        (base / 'www' / 'livraison').mkdir(parents=True)
        for f in SOURCE.glob('*.php'):
            shutil.copy2(f, base / 'www' / 'livraison' / f.name)
        (base / 'routeur.php').write_text(ROUTEUR, encoding='utf-8')
        # l'empreinte de la clé vit hors de la racine web, comme chez OVH
        (base / 'sbt-livraisons.php').write_text(
            "<?php return ['cle' => '%s'];\n" % empreinte(CLE), encoding='utf-8')
        cls.port = port_libre()
        cls.url = 'http://127.0.0.1:%d' % cls.port
        cls.php = subprocess.Popen(
            ['php', '-d', 'upload_max_filesize=4M', '-d', 'post_max_size=6M',
             '-S', '127.0.0.1:%d' % cls.port, '-t', str(base / 'www'), str(base / 'routeur.php')],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            try:
                urllib.request.urlopen(cls.url + '/livraison/api.php?a=etat', timeout=1).read()
                break
            except Exception:
                time.sleep(0.1)
        else:
            cls.php.kill()
            raise unittest.SkipTest('le serveur PHP n’a pas démarré')

    @classmethod
    def tearDownClass(cls):
        cls.php.terminate()
        cls.php.wait(timeout=10)
        cls.temp.cleanup()

    def setUp(self):
        self.photographe = self.navigateur()
        self.jeton = ''
        self.client = self.navigateur()

    def navigateur(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(
            http.cookiejar.CookieJar()))

    # -- petits utilitaires -------------------------------------------------

    def demande(self, ouvreur, chemin, corps=None, type_=None, entetes=None):
        req = urllib.request.Request(self.url + chemin, data=corps, method='POST' if corps is not None else 'GET')
        if type_:
            req.add_header('Content-Type', type_)
        for k, v in (entetes or {}).items():
            req.add_header(k, v)
        try:
            r = ouvreur.open(req, timeout=30)
            return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def api(self, action, corps=None, l=None, jeton=True):
        chemin = '/livraison/api.php?a=' + action + ('&l=' + l if l else '')
        entetes = {'X-Jeton': self.jeton} if (jeton and self.jeton) else {}
        données = json.dumps(corps).encode() if corps is not None else None
        code, brut, _ = self.demande(self.photographe, chemin, données, 'application/json', entetes)
        return code, json.loads(brut.decode('utf-8'))

    def ouvrir_session(self, cle=CLE):
        code, d = self.api('ouvrir', {'cle': cle}, jeton=False)
        if code == 200:
            self.jeton = d['jeton']
        return code, d

    def galerie_prête(self, titre='Tournoi de judo', photos=2):
        self.ouvrir_session()
        _, d = self.api('creer', {'titre': titre})
        ident = d['livraison']['id']
        for i in range(photos):
            type_, corps = multipart(
                {'nom': 'IMG_000%d.jpg' % (i + 1)},
                [('original', 'o.jpg', 'image/jpeg', jpeg(couleur='#%02x77aa' % (0x30 + i * 40))),
                 ('apercu', 'a.jpg', 'image/jpeg', jpeg((1600, 1067)))])
            code, _, _ = self.demande(
                self.photographe, '/livraison/api.php?a=photo&l=' + ident, corps, type_,
                {'X-Jeton': self.jeton})
            self.assertEqual(code, 200)
        return ident

    # -- la porte -----------------------------------------------------------

    def test_la_cle_seule_ouvre_l_administration(self):
        code, d = self.api('liste', jeton=False)
        self.assertEqual(code, 401)
        self.assertEqual(self.ouvrir_session('mauvaise')[0], 401)
        self.assertEqual(self.ouvrir_session()[0], 200)
        self.assertEqual(self.api('liste')[0], 200)

    def test_le_cookie_seul_ne_suffit_pas(self):
        """Un site tiers peut emprunter le cookie, jamais poser l'en-tête."""
        self.ouvrir_session()
        vrai, self.jeton = self.jeton, 'faux'
        self.assertEqual(self.api('liste')[0], 401)
        self.jeton = vrai
        self.assertEqual(self.api('liste')[0], 200)

    def test_un_fichier_php_deguise_en_photo_est_refuse(self):
        self.ouvrir_session()
        _, d = self.api('creer', {'titre': 'Essai'})
        ident = d['livraison']['id']
        type_, corps = multipart({'nom': 'x.jpg'},
                                 [('original', 'x.jpg', 'image/jpeg', b'<?php echo 1; ?>')])
        code, brut, _ = self.demande(self.photographe, '/livraison/api.php?a=photo&l=' + ident,
                                     corps, type_, {'X-Jeton': self.jeton})
        self.assertEqual(code, 400)
        self.assertIn('JPEG', json.loads(brut)['erreur'])
        self.assertEqual(self.api('galerie', l=ident)[1]['livraison']['photos'], [])

    # -- la galerie ---------------------------------------------------------

    def test_les_photos_arrivent_en_ligne(self):
        ident = self.galerie_prête()
        code, d = self.api('galerie', l=ident)
        self.assertEqual(code, 200)
        self.assertEqual([p['nom'] for p in d['livraison']['photos']],
                         ['IMG_0001.jpg', 'IMG_0002.jpg'])
        code, page, _ = self.demande(self.client, '/livraison/%s/' % ident)
        self.assertEqual(code, 200)
        texte = page.decode('utf-8')
        # L'adresse des photos doit partir de /livraison/, sinon le navigateur
        # la cherche sous /livraison/<id>/, où rien n'existe.
        self.assertIn('src="/livraison/fichier.php?l=' + ident, texte)
        self.assertEqual(texte.count('<article>'), 2)

    def test_les_originaux_ne_sont_pas_servis_par_le_serveur(self):
        ident = self.galerie_prête(photos=1)
        photo = self.api('galerie', l=ident)[1]['livraison']['photos'][0]
        code, _, _ = self.demande(self.client, '/livraison/%s/prives/manifeste.json' % ident)
        self.assertEqual(code, 403)
        code, corps, entetes = self.demande(
            self.client, '/livraison/fichier.php?l=%s&o=%s' % (ident, photo['id']))
        self.assertEqual(code, 200)
        self.assertEqual(len(corps), photo['octets'])
        self.assertIn('IMG_0001.jpg', entetes['Content-Disposition'])
        self.assertIn('noindex', entetes['X-Robots-Tag'])

    def test_le_mot_de_passe_ferme_aussi_les_fichiers(self):
        ident = self.galerie_prête(photos=1)
        photo = self.api('galerie', l=ident)[1]['livraison']['photos'][0]
        self.assertEqual(self.api('mdp', {'mdp': 'court'}, l=ident)[0], 400)
        self.assertEqual(self.api('mdp', {'mdp': 'chouette2026'}, l=ident)[0], 200)

        visiteur = self.navigateur()
        code, page, _ = self.demande(visiteur, '/livraison/%s/' % ident)
        self.assertEqual(code, 200)
        self.assertIn('type="password"', page.decode('utf-8'))
        self.assertNotIn('<article>', page.decode('utf-8'))
        for quoi in ('o=' + photo['id'], 'zip=1'):
            self.assertEqual(self.demande(
                visiteur, '/livraison/fichier.php?l=%s&%s' % (ident, quoi))[0], 403)

        self.assertEqual(self.demande(visiteur, '/livraison/%s/' % ident, b'mdp=faux',
                                      'application/x-www-form-urlencoded')[0], 200)
        self.demande(visiteur, '/livraison/%s/' % ident, b'mdp=chouette2026',
                     'application/x-www-form-urlencoded')
        code, page, _ = self.demande(visiteur, '/livraison/%s/' % ident)
        self.assertIn('<article>', page.decode('utf-8'))
        self.assertEqual(self.demande(
            visiteur, '/livraison/fichier.php?l=%s&o=%s' % (ident, photo['id']))[0], 200)

        # une autre galerie protégée reste fermée : la session ne vaut que pour celle-ci
        autre = self.galerie_prête('Autre', photos=1)
        self.api('mdp', {'mdp': 'chouette2026'}, l=autre)
        code, page, _ = self.demande(visiteur, '/livraison/%s/' % autre)
        self.assertIn('type="password"', page.decode('utf-8'))

    def test_l_archive_contient_les_originaux_intacts(self):
        ident = self.galerie_prête(photos=3)
        code, corps, entetes = self.demande(self.client, '/livraison/fichier.php?l=%s&zip=1' % ident)
        self.assertEqual(code, 200)
        self.assertEqual(int(entetes['Content-Length']), len(corps))
        archive = zipfile.ZipFile(io.BytesIO(corps))
        self.assertIsNone(archive.testzip())
        self.assertEqual([e.filename for e in archive.infolist()],
                         ['IMG_0001.jpg', 'IMG_0002.jpg', 'IMG_0003.jpg'])
        for e in archive.infolist():
            octets = archive.read(e.filename)
            self.assertEqual(len(octets), e.file_size)
            self.assertTrue(octets.startswith(b'\xff\xd8'))   # un vrai JPEG
        seule = self.demande(
            self.client, '/livraison/fichier.php?l=%s&o=%s'
            % (ident, self.api('galerie', l=ident)[1]['livraison']['photos'][0]['id']))[1]
        self.assertEqual(archive.read('IMG_0001.jpg'), seule)

    def test_reprise_d_un_telechargement_coupe(self):
        ident = self.galerie_prête(photos=1)
        photo = self.api('galerie', l=ident)[1]['livraison']['photos'][0]
        chemin = '/livraison/fichier.php?l=%s&o=%s' % (ident, photo['id'])
        entier = self.demande(self.client, chemin)[1]
        req = urllib.request.Request(self.url + chemin)
        req.add_header('Range', 'bytes=100-199')
        r = self.client.open(req, timeout=30)
        self.assertEqual(r.status, 206)
        morceau = r.read()
        self.assertEqual(morceau, entier[100:200])

    def test_une_photo_trop_lourde_le_dit_clairement(self):
        """PHP a deux limites, et l'une des deux vide tout sans rien signaler."""
        self.ouvrir_session()
        ident = self.api('creer', {'titre': 'Limites'})[1]['livraison']['id']
        self.assertGreater(self.api('etat', jeton=False)[1]['max_octets'], 0)
        # 5 Mo : au-delà d'upload_max_filesize (4 Mo), PHP signale le fichier
        # 8 Mo : au-delà de post_max_size (6 Mo), PHP vide $_POST et $_FILES
        for taille in (5, 8):
            type_, corps = multipart(
                {'nom': 'enorme.jpg'},
                [('original', 'e.jpg', 'image/jpeg', b'\xff\xd8' + b'\0' * (taille << 20))])
            code, brut, _ = self.demande(self.photographe, '/livraison/api.php?a=photo&l=' + ident,
                                         corps, type_, {'X-Jeton': self.jeton})
            self.assertEqual(code, 413, '%d Mo' % taille)
            self.assertIn('trop lourde', json.loads(brut)['erreur'], '%d Mo' % taille)
        self.assertEqual(self.api('galerie', l=ident)[1]['livraison']['photos'], [])

    def test_retirer_une_photo_puis_la_livraison(self):
        ident = self.galerie_prête(photos=2)
        photos = self.api('galerie', l=ident)[1]['livraison']['photos']
        code, d = self.api('retirer', {'photo': photos[0]['id']}, l=ident)
        self.assertEqual(code, 200)
        self.assertEqual([p['nom'] for p in d['livraison']['photos']], ['IMG_0002.jpg'])
        self.assertEqual(self.api('supprimer', {}, l=ident)[0], 200)
        self.assertEqual(self.api('galerie', l=ident)[0], 404)
        self.assertEqual(self.demande(self.client, '/livraison/%s/' % ident)[0], 404)


if __name__ == '__main__':
    unittest.main()
