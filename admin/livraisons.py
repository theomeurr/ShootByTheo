"""Livraisons locales : originaux hors Git et export statique pour OVH."""
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
            return {'lien': domaine + '/livraison/' + token + '/' if domaine else '',
                    'apercu': '/_livraisons/' + token + '/apercu-' + preview_id + '/index.html',
                    'export': '/api/livraisons/export?id=' + token}


def page(data):
    titre = escape(data['titre'])
    cards = []
    for i, p in enumerate(data['photos'], 1):
        name = escape(p['nom'], quote=True)
        cards.append('<article><button class="photo" data-index="%d" aria-label="Agrandir %s"><img src="apercus/%s.jpg" alt="%s" loading="lazy"></button><div class="caption"><span>%s</span><a href="originaux/%s" download="%s">Télécharger ↓</a></div></article>' %
                     (i-1, name, p['id'], name, name, p['fichier'], name))
    return '''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive"><meta name="referrer" content="no-referrer">
<title>''' + titre + ''' — SHOOTBYTHEO</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#111310;color:#eeeee7;font:16px/1.5 system-ui,sans-serif}header,main,footer{max-width:1440px;margin:auto;padding:32px 5vw}header{border-bottom:1px solid #34382e;display:flex;justify-content:space-between;gap:20px}.brand{font-weight:800;letter-spacing:.12em}.muted{color:#aaaF9f}.intro{padding:36px 0 45px;max-width:850px}h1{font-size:clamp(34px,6vw,72px);line-height:1.1;letter-spacing:-.045em;margin:16px 0 24px}a{color:inherit}button,a{touch-action:manipulation}button{font:inherit;cursor:pointer}.download{display:inline-block;padding:14px 22px;background:#d9edaf;color:#17200c;text-decoration:none;border-radius:6px;font-weight:650;margin-top:12px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px 20px}.photo{width:100%;padding:0;border:0;background:#20241c;border-radius:5px;overflow:hidden;display:block}.photo img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;transition:transform .25s}.photo:hover img{transform:scale(1.025)}.caption{display:flex;justify-content:space-between;gap:10px;font-size:12px;padding-top:10px}.caption span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#acb1a3}.caption a{flex-shrink:0}footer{color:#aaaF9f;font-size:13px;border-top:1px solid #34382e;margin-top:40px}dialog{width:96vw;max-width:1400px;max-height:96vh;border:1px solid #424936;padding:16px;background:#111310;color:#eeeee7}dialog::backdrop{background:#000d}.toolbar{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:10px}.toolbar button{border:1px solid #515946;border-radius:5px;background:#252c1e;color:inherit;padding:10px}#grand{display:block;width:100%;height:72vh;object-fit:contain}button:focus-visible,a:focus-visible{outline:3px solid #d9edaf;outline-offset:4px}@media(max-width:800px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.caption{flex-direction:column}header{font-size:12px}}@media(max-width:480px){.grid{grid-template-columns:1fr}.caption{flex-direction:row}#grand{height:62vh}.toolbar{flex-wrap:wrap}}@media(prefers-reduced-motion:reduce){.photo img{transition:none}}
</style></head><body><header><span class="brand">SHOOTBYTHEO</span><span class="muted">Votre galerie photo</span></header>
<main><section class="intro"><span class="muted">LIVRAISON · ''' + str(len(data['photos'])) + ''' PHOTOS</span><h1>''' + titre + '''</h1><p>Vos images sont prêtes. Prenez le temps de les découvrir et téléchargez vos fichiers en qualité originale.</p><a class="download" href="photos.zip" download>Télécharger toutes les photos ↓</a></section>
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
