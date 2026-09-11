"""Livraisons locales : originaux hors Git et export statique pour OVH."""
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlsplit


class Livraisons:
    def __init__(self, root):
        self.root = Path(root) / '_livraisons'
        self.lock = threading.RLock()

    def dossier(self, token):
        if not re.fullmatch(r'[a-f0-9]{32}', token or ''):
            raise ValueError('Lien de livraison invalide.')
        path = self.root / token
        if path.is_symlink():
            raise ValueError('Dossier de livraison invalide.')
        return path

    def lire(self, token):
        return json.loads((self.dossier(token) / 'galerie.json').read_text(encoding='utf-8'))

    def sauver(self, data):
        path = self.dossier(data['id']) / 'galerie.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, path)

    def liste(self):
        with self.lock:
            return sorted([self.lire(p.parent.name) for p in self.root.glob('*/galerie.json')
                           if re.fullmatch(r'[a-f0-9]{32}', p.parent.name)],
                          key=lambda d: d['date'], reverse=True)

    def creer(self, titre):
        titre = str(titre or '').strip()
        if not titre or len(titre) > 200:
            raise ValueError('Indiquez un titre de 1 à 200 caractères.')
        with self.lock:
            token = secrets.token_hex(16)
            self.dossier(token).mkdir(parents=True)
            data = {'id': token, 'titre': titre, 'date': datetime.now(timezone.utc).isoformat(), 'photos': []}
            self.sauver(data)
            return data

    def ajouter(self, token, name, body):
        from PIL import Image, ImageOps
        if not body or len(body) > 100 * 1024 * 1024:
            raise ValueError('Chaque photo doit peser moins de 100 Mo.')
        with self.lock:
            data = self.lire(token)
            with Image.open(io.BytesIO(body)) as source:
                ext = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}.get(source.format)
                if not ext:
                    raise ValueError('Utilisez des photos JPEG, PNG ou WebP.')
                source.load()
                preview = ImageOps.exif_transpose(source).convert('RGB')
                preview.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                pid = secrets.token_hex(16)
                folder = self.dossier(token)
                (folder / 'originaux').mkdir(exist_ok=True)
                (folder / 'apercus').mkdir(exist_ok=True)
                (folder / 'originaux' / (pid + ext)).write_bytes(body)
                preview.save(folder / 'apercus' / (pid + '.jpg'), 'JPEG', quality=85)
            data['photos'].append({'id': pid, 'nom': str(name).replace('\\', '/').split('/')[-1][:200],
                                   'fichier': pid + ext, 'octets': len(body)})
            self.sauver(data)
            return data

    # Le mot de passe n'est jamais conservé : seule son empreinte l'est, et
    # elle ne permet pas de le retrouver. Même format que le reste du projet,
    # vérifiable par hash_pbkdf2() côté PHP.
    TOURS = 210000

    def definir_mdp(self, token, motdepasse):
        motdepasse = str(motdepasse or '')
        with self.lock:
            data = self.lire(token)
            if not motdepasse:
                data.pop('mdp', None)
            else:
                if len(motdepasse) < 6:
                    raise ValueError('Choisissez un mot de passe d\'au moins 6 caractères.')
                sel = secrets.token_bytes(16)
                h = hashlib.pbkdf2_hmac('sha256', motdepasse.encode('utf-8'), sel, self.TOURS)
                data['mdp'] = 'pbkdf2$sha256$%d$%s$%s' % (self.TOURS, sel.hex(), h.hex())
            self.sauver(data)
            return data

    def preparer(self, token, domaine):
        with self.lock:
            data = self.lire(token)
            if not data['photos']:
                raise ValueError('Ajoutez au moins une photo avant de préparer la livraison.')
            domaine = str(domaine or '').strip().rstrip('/')
            if domaine and '://' not in domaine:
                domaine = 'https://' + domaine
            url = urlsplit(domaine)
            if domaine and (url.scheme != 'https' or not url.hostname or url.query or url.fragment or url.username):
                raise ValueError('Renseignez une adresse HTTPS valide dans les réglages du site.')
            folder = self.dossier(token)
            # Un export indépendant : aucune photo client ne passe dans data.js ou GitHub.
            with tempfile.TemporaryDirectory(dir=folder) as temp:
                public = Path(temp) / 'public'
                public.mkdir()
                (public / 'originaux').mkdir()
                (public / 'apercus').mkdir()
                with zipfile.ZipFile(public / 'photos.zip', 'w', compression=zipfile.ZIP_STORED) as archive:
                    for i, photo in enumerate(data['photos'], 1):
                        source = folder / 'originaux' / photo['fichier']
                        shutil.copy2(source, public / 'originaux' / photo['fichier'])
                        shutil.copy2(folder / 'apercus' / (photo['id'] + '.jpg'), public / 'apercus' / (photo['id'] + '.jpg'))
                        # Préfixe numérique pour préserver les noms doublons, sans chemins dans le ZIP.
                        name = re.sub(r'[^\w. -]', '_', photo['nom']) or photo['fichier']
                        archive.write(source, '%03d-%s' % (i, name))
                protege = bool(data.get('mdp'))
                if protege:
                    # Les photos passent sous « prives/ », qu'Apache refuse de
                    # servir : sans cela, l'adresse d'un original suffirait à
                    # contourner la page de mot de passe.
                    prives = public / 'prives'
                    prives.mkdir()
                    for nom in ('originaux', 'apercus'):
                        shutil.move(str(public / nom), str(prives / nom))
                    shutil.move(str(public / 'photos.zip'), str(prives / 'photos.zip'))
                    (prives / 'galerie.html').write_text(page(data, True), encoding='utf-8')
                    (prives / '.htaccess').write_text(HTACCESS_PRIVES, encoding='utf-8')
                    inventaire = [{'id': ph['id'], 'nom': ph['nom'], 'fichier': ph['fichier']}
                                  for ph in data['photos']]
                    (public / 'garde.php').write_text(
                        GARDE_PHP.replace('__EMPREINTE__', php_texte(data['mdp']))
                                 .replace('__PHOTOS__', php_tableau(inventaire))
                                 .replace('__ZIP__', php_texte(nom_zip(data['titre']))),
                        encoding='utf-8')
                    (public / 'index.php').write_text(
                        INDEX_PHP.replace('__TITRE__', escape(data['titre'])), encoding='utf-8')
                    (public / 'fichier.php').write_text(FICHIER_PHP, encoding='utf-8')
                    (public / '.htaccess').write_text(HTACCESS_PROTEGE, encoding='utf-8')
                else:
                    (public / 'index.html').write_text(page(data), encoding='utf-8')
                    (public / '.htaccess').write_text('Options -Indexes\n<IfModule mod_headers.c>\nHeader set X-Robots-Tag "noindex, nofollow, noarchive"\nHeader set Referrer-Policy "no-referrer"\n</IfModule>\n', encoding='utf-8')
                archive_tmp = folder / 'export.tmp'
                with zipfile.ZipFile(archive_tmp, 'w', compression=zipfile.ZIP_STORED) as archive:
                    for path in public.rglob('*'):
                        if path.is_file():
                            archive.write(path, 'livraison/' + token + '/' + path.relative_to(public).as_posix())
                # Chaque aperçu porte un identifiant propre, donc un export suivant ne le remplace pas.
                preview_id = secrets.token_hex(16)
                destination = folder / ('apercu-' + preview_id)
                shutil.move(str(public), destination)
                os.replace(archive_tmp, folder / 'export.zip')
            # Un aperçu contient une copie entière des originaux : les garder
            # tous ferait grossir le disque d'une livraison complète à chaque
            # export. Le nouveau est en place, les précédents ne servent plus.
            for ancien in folder.glob('apercu-*'):
                if ancien != destination and ancien.is_dir() and not ancien.is_symlink():
                    shutil.rmtree(ancien, ignore_errors=True)
            return {'protege': bool(data.get('mdp')),
                    'lien': domaine + '/livraison/' + token + '/' if domaine else '',
                    'apercu': '/_livraisons/' + token + '/apercu-' + preview_id
                              + ('/prives/galerie.html' if data.get('mdp') else '/index.html'),
                    'export': '/api/livraisons/export?id=' + token}


# ---------------------------------------------------------------- protection
# Une galerie protégée n'est plus servie en fichiers statiques : Apache refuse
# l'accès direct aux photos, et PHP ne les diffuse qu'une fois le mot de passe
# donné. Sans cela, l'adresse d'un original suffirait à contourner la page.
GARDE_PHP = r"""<?php
// Fichier produit par l'administration SHOOTBYTHEO — ne pas modifier.
declare(strict_types=1);

const SBT_EMPREINTE = __EMPREINTE__;
const SBT_PHOTOS = __PHOTOS__;
const SBT_ZIP = __ZIP__;

function sbt_prives(): string { return __DIR__ . '/prives'; }

function sbt_https(): bool {
    return !empty($_SERVER['HTTPS'])
        || ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https'
        || (string)($_SERVER['SERVER_PORT'] ?? '') === '443';
}

function sbt_session(): void {
    if (session_status() === PHP_SESSION_ACTIVE) { return; }
    // le cookie ne vaut que pour cette galerie : ouvrir l'une n'ouvre pas l'autre
    $base = rtrim(str_replace('\\', '/', dirname((string)($_SERVER['SCRIPT_NAME'] ?? '/'))), '/') . '/';
    session_name('sbt_livraison');
    session_set_cookie_params(['lifetime' => 0, 'path' => $base,
        'secure' => sbt_https(), 'httponly' => true, 'samesite' => 'Lax']);
    session_start();
}

function sbt_ouverte(): bool { sbt_session(); return !empty($_SESSION['ouverte']); }

function sbt_ouvrir(): void {
    sbt_session();
    session_regenerate_id(true);
    $_SESSION['ouverte'] = true;
}

function sbt_mdp_correct(string $saisi): bool {
    $e = SBT_EMPREINTE;
    if (strncmp($e, 'pbkdf2$', 7) === 0) {
        $p = explode('$', $e);
        if (count($p) !== 5) { return false; }
        [, $algo, $tours, $sel, $attendu] = $p;
        if (!in_array($algo, ['sha256', 'sha512'], true) || !ctype_xdigit($sel)
            || !ctype_xdigit($attendu) || (int)$tours < 1000) { return false; }
        return hash_equals($attendu,
            hash_pbkdf2($algo, $saisi, (string)hex2bin($sel), (int)$tours, 0, false));
    }
    return password_verify($saisi, $e);
}

function sbt_essais(): string {
    return sys_get_temp_dir() . '/sbt-liv-' . substr(sha1(__DIR__), 0, 12);
}

/** Secondes à patienter, 0 si l'essai est permis. */
function sbt_attente(): int {
    $t = @json_decode((string)@file_get_contents(sbt_essais()), true);
    if (!is_array($t)) { return 0; }
    $recents = array_filter($t, function ($h) { return $h > time() - 1800; });
    $n = count($recents);
    if ($n < 3) { return 0; }   // trois essais francs pour une faute de frappe
    return max(0, (min(300, 5 * (2 ** ($n - 3))) + max($recents)) - time());
}

function sbt_echec(): void {
    $t = @json_decode((string)@file_get_contents(sbt_essais()), true);
    $t = is_array($t) ? array_filter($t, function ($h) { return $h > time() - 1800; }) : [];
    $t[] = time();
    @file_put_contents(sbt_essais(), json_encode(array_values($t)), LOCK_EX);
}

function sbt_oublier(): void { @unlink(sbt_essais()); }

/**
 * Diffuse un fichier privé. Les téléchargements d'une galerie entière peuvent
 * peser plusieurs gigaoctets : la lecture est découpée, et une reprise après
 * coupure est acceptée plutôt que de tout refaire.
 */
function sbt_envoyer(string $chemin, string $nom, string $type, bool $inline): void {
    if (!is_file($chemin)) { http_response_code(404); exit; }
    $taille = (int)filesize($chemin);
    $debut = 0;
    $fin = $taille - 1;
    $partiel = false;
    $plage = (string)($_SERVER['HTTP_RANGE'] ?? '');
    if ($plage !== '' && preg_match('/^bytes=(\d*)-(\d*)$/', $plage, $m)) {
        if ($m[1] === '' && $m[2] !== '') {
            $debut = max(0, $taille - (int)$m[2]);
        } else {
            $debut = (int)$m[1];
            if ($m[2] !== '') { $fin = min($fin, (int)$m[2]); }
        }
        if ($debut > $fin || $debut >= $taille) {
            http_response_code(416);
            header('Content-Range: bytes */' . $taille);
            exit;
        }
        $partiel = true;
    }
    while (ob_get_level() > 0) { ob_end_clean(); }
    http_response_code($partiel ? 206 : 200);
    header('Content-Type: ' . $type);
    header('Accept-Ranges: bytes');
    header('Content-Length: ' . (string)($fin - $debut + 1));
    header('Cache-Control: private, max-age=600');
    header('X-Robots-Tag: noindex, nofollow, noarchive');
    if ($partiel) { header(sprintf('Content-Range: bytes %d-%d/%d', $debut, $fin, $taille)); }
    header('Content-Disposition: ' . ($inline ? 'inline' : 'attachment')
        . '; filename*=UTF-8\'\'' . rawurlencode($nom));
    $f = fopen($chemin, 'rb');
    if ($f === false) { exit; }
    fseek($f, $debut);
    $reste = $fin - $debut + 1;
    while ($reste > 0 && !feof($f) && !connection_aborted()) {
        $bloc = fread($f, (int)min(262144, $reste));
        if ($bloc === false || $bloc === '') { break; }
        echo $bloc;
        flush();
        $reste -= strlen($bloc);
    }
    fclose($f);
    exit;
}
"""

INDEX_PHP = r"""<?php
// Fichier produit par l'administration SHOOTBYTHEO — ne pas modifier.
declare(strict_types=1);
require __DIR__ . '/garde.php';

$erreur = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && !sbt_ouverte()) {
    $attente = sbt_attente();
    if ($attente > 0) {
        $erreur = 'Trop de tentatives. Réessayez dans '
            . ($attente > 60 ? (string)(int)ceil($attente / 60) . ' minutes'
                             : (string)$attente . ' secondes') . '.';
    } elseif (sbt_mdp_correct((string)($_POST['mdp'] ?? ''))) {
        sbt_oublier();
        sbt_ouvrir();
        header('Location: ./');
        exit;
    } else {
        sbt_echec();
        $erreur = 'Mot de passe incorrect.';
    }
}

header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
header('X-Robots-Tag: noindex, nofollow, noarchive');
header('Referrer-Policy: no-referrer');

if (sbt_ouverte()) {
    readfile(sbt_prives() . '/galerie.html');
    exit;
}
?>
<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="referrer" content="no-referrer">
<title>__TITRE__ — SHOOTBYTHEO</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
padding:24px;background:#111310;color:#eeeee7;font:16px/1.6 system-ui,sans-serif}
.boite{width:100%;max-width:360px}
.marque{font-weight:800;letter-spacing:.12em;font-size:13px;text-align:center}
h1{font-size:22px;line-height:1.25;margin:14px 0 6px;text-align:center}
p{color:#acb1a3;font-size:13.5px;margin:0 0 22px;text-align:center}
label{display:block;font-size:13px;font-weight:600;margin-bottom:6px}
input{width:100%;background:#20241c;border:1px solid #424936;border-radius:6px;
color:inherit;font-size:16px;padding:13px 14px;outline:none}
input:focus{border-color:#d9edaf}
button{width:100%;margin-top:14px;border:0;border-radius:6px;background:#d9edaf;
color:#17200c;font:inherit;font-weight:650;padding:14px;cursor:pointer}
button:hover{filter:brightness(1.05)}
.ko{background:#3a201c;border:1px solid #7c3b31;border-radius:6px;padding:11px 13px;
font-size:13.5px;margin-bottom:18px;color:#f3c3b8}
.pied{margin-top:20px;font-size:12px;color:#8d9285;text-align:center}
button:focus-visible,input:focus-visible{outline:3px solid #d9edaf;outline-offset:3px}
</style></head><body>
<div class="boite">
  <div class="marque">SHOOTBYTHEO</div>
  <h1>__TITRE__</h1>
  <p>Cette galerie est protégée. Entrez le mot de passe qui vous a été communiqué.</p>
<?php if ($erreur !== ''): ?>
  <div class="ko"><?= htmlspecialchars($erreur, ENT_QUOTES) ?></div>
<?php endif; ?>
  <form method="POST" autocomplete="on">
    <label for="mdp">Mot de passe</label>
    <input id="mdp" name="mdp" type="password" autocomplete="current-password" required autofocus>
    <button type="submit">Voir mes photos</button>
  </form>
  <div class="pied">SHOOTBYTHEO — photographie sportive</div>
</div></body></html>
"""

FICHIER_PHP = r"""<?php
// Fichier produit par l'administration SHOOTBYTHEO — ne pas modifier.
declare(strict_types=1);
require __DIR__ . '/garde.php';

if (!sbt_ouverte()) {
    http_response_code(403);
    header('Content-Type: text/plain; charset=utf-8');
    exit("Accès refusé : ouvrez d'abord la galerie.");
}

$types = ['jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg',
          'png' => 'image/png', 'webp' => 'image/webp'];

if (isset($_GET['zip'])) {
    sbt_envoyer(sbt_prives() . '/photos.zip', SBT_ZIP, 'application/zip', false);
}

// L'identifiant demandé est comparé au inventaire : aucun chemin ne vient de
// l'adresse, donc aucune sortie possible du dossier.
$apercu = (string)($_GET['a'] ?? '');
$original = (string)($_GET['o'] ?? '');
foreach (SBT_PHOTOS as $photo) {
    if ($apercu !== '' && hash_equals($photo['id'], $apercu)) {
        sbt_envoyer(sbt_prives() . '/apercus/' . $photo['id'] . '.jpg',
                    $photo['nom'], 'image/jpeg', true);
    }
    if ($original !== '' && hash_equals($photo['id'], $original)) {
        $ext = strtolower((string)pathinfo($photo['fichier'], PATHINFO_EXTENSION));
        sbt_envoyer(sbt_prives() . '/originaux/' . $photo['fichier'], $photo['nom'],
                    $types[$ext] ?? 'application/octet-stream', false);
    }
}
http_response_code(404);
header('Content-Type: text/plain; charset=utf-8');
exit('Photo introuvable.');
"""

HTACCESS_PROTEGE = """Options -Indexes
DirectoryIndex index.php
<IfModule mod_headers.c>
Header set X-Robots-Tag "noindex, nofollow, noarchive"
Header set Referrer-Policy "no-referrer"
</IfModule>
# garde.php porte l'empreinte du mot de passe : il n'est jamais servi tel quel.
<FilesMatch "^garde\\.php$">
  Require all denied
</FilesMatch>
<IfModule !mod_authz_core.c>
  <FilesMatch "^garde\\.php$">
    Order allow,deny
    Deny from all
  </FilesMatch>
</IfModule>
"""

# Les photos vivent ici ; Apache ne doit jamais les servir directement. PHP les
# lit par le système de fichiers, que cette règle ne concerne pas.
HTACCESS_PRIVES = """Options -Indexes
Require all denied
<IfModule !mod_authz_core.c>
  Order allow,deny
  Deny from all
</IfModule>
"""


def php_texte(valeur):
    """Littéral PHP à guillemets simples, sûr quel que soit le contenu."""
    return "'" + str(valeur).replace('\\', '\\\\').replace("'", "\\'") + "'"


def php_tableau(lignes):
    return '[' + ', '.join(
        '[' + ', '.join('%s => %s' % (php_texte(k), php_texte(v)) for k, v in l.items()) + ']'
        for l in lignes) + ']'


def nom_zip(titre):
    base = re.sub(r'\s+', ' ', re.sub(r'[^\w -]', ' ', str(titre))).strip() or 'photos'
    return base[:60].strip() + '.zip'


def page(data, protege=False):
    titre = escape(data['titre'])
    # Protégée, la galerie ne désigne plus les fichiers : elle demande une photo
    # par son identifiant, et PHP la sert après avoir vérifié la session.
    apercu = (lambda q: 'fichier.php?a=' + q) if protege else (lambda q: 'apercus/' + q + '.jpg')
    zip_url = 'fichier.php?zip=1' if protege else 'photos.zip'
    cards = []
    for i, p in enumerate(data['photos'], 1):
        name = escape(p['nom'], quote=True)
        lien = ('fichier.php?o=' + p['id']) if protege else ('originaux/' + p['fichier'])
        cards.append('<article><button class="photo" data-index="%d" aria-label="Agrandir %s"><img src="%s" alt="%s" loading="lazy"></button><div class="caption"><span>%s</span><a href="%s" download="%s">Télécharger ↓</a></div></article>' %
                     (i-1, name, apercu(p['id']), name, name, lien, name))
    return '''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive"><meta name="referrer" content="no-referrer">
<title>''' + titre + ''' — SHOOTBYTHEO</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#111310;color:#eeeee7;font:16px/1.5 system-ui,sans-serif}header,main,footer{max-width:1440px;margin:auto;padding:32px 5vw}header{border-bottom:1px solid #34382e;display:flex;justify-content:space-between;gap:20px}.brand{font-weight:800;letter-spacing:.12em}.muted{color:#aaaF9f}.intro{padding:36px 0 45px;max-width:850px}h1{font-size:clamp(34px,6vw,72px);line-height:1.1;letter-spacing:-.045em;margin:16px 0 24px}a{color:inherit}button,a{touch-action:manipulation}button{font:inherit;cursor:pointer}.download{display:inline-block;padding:14px 22px;background:#d9edaf;color:#17200c;text-decoration:none;border-radius:6px;font-weight:650;margin-top:12px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px 20px}.photo{width:100%;padding:0;border:0;background:#20241c;border-radius:5px;overflow:hidden;display:block}.photo img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;transition:transform .25s}.photo:hover img{transform:scale(1.025)}.caption{display:flex;justify-content:space-between;gap:10px;font-size:12px;padding-top:10px}.caption span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#acb1a3}.caption a{flex-shrink:0}footer{color:#aaaF9f;font-size:13px;border-top:1px solid #34382e;margin-top:40px}dialog{width:96vw;max-width:1400px;max-height:96vh;border:1px solid #424936;padding:16px;background:#111310;color:#eeeee7}dialog::backdrop{background:#000d}.toolbar{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:10px}.toolbar button{border:1px solid #515946;border-radius:5px;background:#252c1e;color:inherit;padding:10px}#grand{display:block;width:100%;height:72vh;object-fit:contain}button:focus-visible,a:focus-visible{outline:3px solid #d9edaf;outline-offset:4px}@media(max-width:800px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.caption{flex-direction:column}header{font-size:12px}}@media(max-width:480px){.grid{grid-template-columns:1fr}.caption{flex-direction:row}#grand{height:62vh}.toolbar{flex-wrap:wrap}}@media(prefers-reduced-motion:reduce){.photo img{transition:none}}
</style></head><body><header><span class="brand">SHOOTBYTHEO</span><span class="muted">Votre galerie photo</span></header>
<main><section class="intro"><span class="muted">LIVRAISON · ''' + str(len(data['photos'])) + ''' PHOTOS</span><h1>''' + titre + '''</h1><p>Vos images sont prêtes. Prenez le temps de les découvrir et téléchargez vos fichiers en qualité originale.</p><a class="download" href="''' + zip_url + '''" download>Télécharger toutes les photos ↓</a></section>
<section class="grid" aria-label="Photos de la livraison">''' + ''.join(cards) + '''</section></main>
<footer>Galerie accessible aux personnes possédant ce lien. Conservez une copie de vos photos.</footer>
<dialog aria-label="Photo agrandie"><div class="toolbar"><button id="prev" aria-label="Photo précédente">←</button><span id="compteur"></span><a id="original" download>Télécharger l’original ↓</a><button id="next" aria-label="Photo suivante">→</button><button id="fermer">Fermer ×</button></div><img id="grand" alt=""></dialog>
<script>
const photos=Array.from(document.querySelectorAll('article')),dialog=document.querySelector('dialog');let index=0;
function afficher(n){index=(n+photos.length)%photos.length;const card=photos[index],img=card.querySelector('img'),link=card.querySelector('a');document.querySelector('#grand').src=img.src;document.querySelector('#grand').alt=img.alt;document.querySelector('#original').href=link.href;document.querySelector('#original').download=link.download;document.querySelector('#compteur').textContent=(index+1)+' / '+photos.length;}
document.querySelectorAll('.photo').forEach((b,i)=>b.addEventListener('click',()=>{afficher(i);dialog.showModal();}));
document.querySelector('#prev').onclick=()=>afficher(index-1);document.querySelector('#next').onclick=()=>afficher(index+1);document.querySelector('#fermer').onclick=()=>dialog.close();
dialog.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'){e.preventDefault();afficher(index-1);}if(e.key==='ArrowRight'){e.preventDefault();afficher(index+1);}});
</script></body></html>'''
