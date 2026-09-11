"""python3 -m unittest discover -s admin -p 'test_*.py'"""
import io
import tempfile
import json
import pathlib
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from livraisons import Livraisons


class LivraisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Livraisons(self.temp.name)
        self.gallery = self.store.creer('Camille <script>alert(1)</script> & Alex')
        out = io.BytesIO()
        Image.new('RGB', (2100, 3100), '#789abc').save(out, 'JPEG')
        self.photo = out.getvalue()

    def test_export_preserves_originals_and_duplicate_names(self):
        token = self.gallery['id']
        self.store.ajouter(token, 'portrait.jpg', self.photo)
        data = self.store.ajouter(token, 'portrait.jpg', self.photo)
        result = self.store.preparer(token, 'https://photos.example/portfolio/')
        self.assertEqual(result['lien'], 'https://photos.example/portfolio/livraison/' + token + '/')
        folder = self.store.dossier(token)
        with zipfile.ZipFile(folder / 'export.zip') as archive:
            prefix = 'livraison/' + token + '/'
            self.assertTrue(all(n.startswith(prefix) for n in archive.namelist()))
            self.assertNotIn(prefix + 'galerie.json', archive.namelist())
            self.assertEqual(archive.read(prefix + 'originaux/' + data['photos'][0]['fichier']), self.photo)
            html = archive.read(prefix + 'index.html').decode()
            self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
            self.assertIn('noindex, nofollow, noarchive', html)
            self.assertNotIn('<script>alert(1)</script>', html)
            with zipfile.ZipFile(io.BytesIO(archive.read(prefix + 'photos.zip'))) as photos:
                self.assertEqual(photos.namelist(), ['001-portrait.jpg', '002-portrait.jpg'])
                self.assertTrue(all(photos.read(n) == self.photo for n in photos.namelist()))
            with Image.open(io.BytesIO(archive.read(prefix + 'apercus/' + data['photos'][0]['id'] + '.jpg'))) as preview:
                self.assertEqual(max(preview.size), 1600)
        self.assertFalse((Path(self.temp.name) / 'data.js').exists())
        self.assertEqual(len(self.store.liste()[0]['photos']), 2)
        self.assertTrue((Path(self.temp.name) / result['apercu'].lstrip('/')).exists())

    def test_validation_and_empty_gallery(self):
        for token in ['../outside', '', 'a' * 31, 'x' * 32]:
            with self.assertRaises(ValueError):
                self.store.dossier(token)
        with self.assertRaises(ValueError):
            self.store.preparer(self.gallery['id'], 'example.com')
        with self.assertRaises(Exception):
            self.store.ajouter(self.gallery['id'], 'bad.jpg', b'not an image')
        self.assertEqual(self.store.lire(self.gallery['id'])['photos'], [])
        self.store.ajouter(self.gallery['id'], '../../portrait.jpg', self.photo)
        self.assertEqual(self.store.lire(self.gallery['id'])['photos'][0]['nom'], 'portrait.jpg')
        with self.assertRaises(ValueError):
            self.store.preparer(self.gallery['id'], 'javascript://bad')
        self.assertEqual(self.store.preparer(self.gallery['id'], '')['lien'], '')

    def test_separate_unpredictable_links_and_stable_exports(self):
        other = self.store.creer('Autre client')
        self.assertNotEqual(self.gallery['id'], other['id'])
        self.assertRegex(other['id'], r'^[a-f0-9]{32}$')
        self.store.ajouter(self.gallery['id'], 'photo.jpg', self.photo)
        first = self.store.preparer(self.gallery['id'], 'example.com')
        second = self.store.preparer(self.gallery['id'], 'example.com')
        self.assertEqual(first['lien'], second['lien'])
        self.assertNotEqual(first['apercu'], second['apercu'])
        self.assertEqual(self.store.lire(other['id'])['photos'], [])

    def test_mot_de_passe_protege_les_fichiers(self):
        """Une galerie protégée met ses photos hors de portée d'Apache."""
        self.store.ajouter(self.gallery['id'], 'photo.jpg', self.photo)

        libre = self.store.preparer(self.gallery['id'], 'example.com')
        self.assertFalse(libre['protege'])
        dossier = pathlib.Path(self.temp.name) / "_livraisons" / self.gallery['id']
        export = sorted(dossier.glob('apercu-*'))[-1]
        self.assertTrue((export / 'index.html').is_file())
        self.assertFalse((export / 'prives').exists())

        with self.assertRaises(ValueError):
            self.store.definir_mdp(self.gallery['id'], 'court')

        data = self.store.definir_mdp(self.gallery['id'], 'un-bon-mot-de-passe')
        self.assertRegex(data['mdp'], r'^pbkdf2\$sha256\$\d+\$[a-f0-9]+\$[a-f0-9]+$')
        self.assertNotIn('un-bon-mot-de-passe', json.dumps(data))

        protege = self.store.preparer(self.gallery['id'], 'example.com')
        self.assertTrue(protege['protege'])
        self.assertEqual(libre['lien'], protege['lien'])   # le lien ne change pas
        export = sorted(dossier.glob('apercu-*'))[-1]

        # les photos ne sont plus servies directement, et Apache refuse le dossier
        self.assertFalse((export / 'originaux').exists())
        self.assertFalse((export / 'photos.zip').exists())
        self.assertTrue((export / 'prives' / 'photos.zip').is_file())
        self.assertIn('Require all denied', (export / 'prives' / '.htaccess').read_text())
        for nom in ('index.php', 'fichier.php', 'garde.php'):
            self.assertTrue((export / nom).is_file())
        # l'empreinte n'est ni servie ni devinable depuis la page
        self.assertIn('Require all denied', (export / '.htaccess').read_text())
        self.assertNotIn(data['mdp'], (export / 'prives' / 'galerie.html').read_text())
        # la page ne désigne plus les fichiers, elle passe par le portier
        galerie = (export / 'prives' / 'galerie.html').read_text()
        self.assertIn('fichier.php?a=', galerie)
        self.assertNotIn('src="apercus/', galerie)

    def test_retrait_du_mot_de_passe(self):
        self.store.ajouter(self.gallery['id'], 'photo.jpg', self.photo)
        self.store.definir_mdp(self.gallery['id'], 'un-bon-mot-de-passe')
        data = self.store.definir_mdp(self.gallery['id'], '')
        self.assertNotIn('mdp', data)
        self.assertFalse(self.store.preparer(self.gallery['id'], 'example.com')['protege'])

    def test_un_seul_apercu_conserve(self):
        """Chaque export copie les originaux : les anciens doivent disparaître."""
        self.store.ajouter(self.gallery['id'], 'photo.jpg', self.photo)
        dossier = pathlib.Path(self.temp.name) / "_livraisons" / self.gallery['id']
        for _ in range(3):
            self.store.preparer(self.gallery['id'], 'example.com')
        self.assertEqual(len(list(dossier.glob('apercu-*'))), 1)


if __name__ == '__main__':
    unittest.main()
