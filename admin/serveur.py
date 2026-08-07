#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serveur d'administration local du site SHOOTBYTHEO.

Usage :
  python3 admin/serveur.py [racine] [port] [--open]

Sans argument : sert le dossier du site (parent de ce dossier) sur
http://127.0.0.1:8737 — interface d'administration sur /admin.

Ce serveur est strictement local (127.0.0.1). Il ne doit JAMAIS être
hébergé en ligne : n'envoyez pas le dossier admin/ chez votre hébergeur.
"""
import io
import json
import os
import re
import shutil
import sys
import threading
import unicodedata
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ADMIN_DIR = os.path.dirname(os.path.abspath(__file__))

_args = [a for a in sys.argv[1:] if a != '--open']
OPEN = '--open' in sys.argv
ROOT = os.path.abspath(_args[0]) if len(_args) > 0 else os.path.dirname(ADMIN_DIR)
PORT = int(_args[1]) if len(_args) > 1 else 8737

DATA_JS = os.path.join(ROOT, 'data.js')
IMG_DIR = os.path.join(ROOT, 'image')
GAL_DIR = os.path.join(IMG_DIR, 'galerie')
WEB_DIR = os.path.join(IMG_DIR, 'web')
ACCUEIL_DIR = os.path.join(IMG_DIR, 'accueil')
TRASH_DIR = os.path.join(IMG_DIR, 'corbeille')

EXT_IMAGES = ('.jpg', '.jpeg', '.png', '.webp')

LARGEUR_MAX = 2000   # côté long des photos publiées sur le site
QUALITE = 80


def slug(text):
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-zA-Z0-9]+', '-', text).strip('-').lower()


def read_data():
    if not os.path.isfile(DATA_JS):
        return {'slides': [], 'series': []}
    with open(DATA_JS, encoding='utf-8') as f:
        txt = f.read()
    m = re.search(r'\{.*\}', txt, re.S)
    return json.loads(m.group(0)) if m else {'slides': [], 'series': []}


def write_data(d):
    tmp = DATA_JS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('window.SITE_DATA = ' + json.dumps(d, ensure_ascii=False, indent=2) + ';\n')
    os.replace(tmp, DATA_JS)


def unique_path(dirpath, base, ext):
    out = os.path.join(dirpath, base + ext)
    n = 2
    while os.path.exists(out):
        out = os.path.join(dirpath, '%s-%d%s' % (base, n, ext))
        n += 1
    return out


class Admin(SimpleHTTPRequestHandler):

    def log_message(self, fmt, *a):
        pass  # pas de bruit dans le terminal

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/admin', '/admin/'):
            with open(os.path.join(ADMIN_DIR, 'interface.html'), 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == '/api/data':
            return self._json(read_data())
        if path == '/api/images':
            return self._json(self._images())
        return super().do_GET()

    def _images(self):
        """Images réutilisables : celles envoyées pour l'accueil, et les images du site."""
        def lister(dirpath):
            if not os.path.isdir(dirpath):
                return []
            noms = [n for n in sorted(os.listdir(dirpath))
                    if n.lower().endswith(EXT_IMAGES) and not n.startswith('.')]
            return [os.path.relpath(os.path.join(dirpath, n), ROOT).replace(os.sep, '/')
                    for n in noms]
        return {'accueil': lister(ACCUEIL_DIR), 'web': lister(WEB_DIR)}

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length)
        try:
            if u.path == '/api/data':
                write_data(json.loads(body.decode('utf-8')))
                return self._json({'ok': True})
            if u.path == '/api/upload':
                return self._json(self._upload(q, body))
            if u.path == '/api/trash':
                return self._json(self._trash(json.loads(body.decode('utf-8'))))
        except Exception as e:  # renvoyé à l'interface, jamais silencieux
            return self._json({'erreur': str(e)}, 500)
        self._json({'erreur': 'requête inconnue'}, 404)

    def _upload(self, q, body):
        try:
            from PIL import Image, ImageOps
        except ImportError:
            raise RuntimeError("Pillow est requis : python3 -m pip install Pillow")
        name = (q.get('name') or ['photo'])[0]
        im = Image.open(io.BytesIO(body))
        im = ImageOps.exif_transpose(im).convert('RGB')
        if im.width > LARGEUR_MAX:
            im = im.resize((LARGEUR_MAX, round(im.height * LARGEUR_MAX / im.width)), Image.LANCZOS)
        dossier = (q.get('dossier') or [''])[0]
        if dossier in ('accueil', 'apropos'):
            dest_dir = os.path.join(IMG_DIR, dossier)
        else:
            serie = slug((q.get('serie') or ['galerie'])[0]) or 'galerie'
            dest_dir = os.path.join(GAL_DIR, serie)
        os.makedirs(dest_dir, exist_ok=True)
        base = slug(os.path.splitext(os.path.basename(name))[0]) or 'photo'
        out = unique_path(dest_dir, base, '.jpg')
        im.save(out, 'JPEG', quality=QUALITE, optimize=True, progressive=True)
        return {'src': os.path.relpath(out, ROOT).replace(os.sep, '/'),
                'largeur': im.width, 'hauteur': im.height}

    def _trash(self, payload):
        srcs = payload.get('srcs') or ([payload['src']] if payload.get('src') else [])
        os.makedirs(TRASH_DIR, exist_ok=True)
        deplacees = []
        for src in srcs:
            p = os.path.realpath(os.path.join(ROOT, src))
            # sécurité : on ne touche qu'aux fichiers du dossier image/
            if not p.startswith(os.path.realpath(IMG_DIR) + os.sep):
                continue
            if not os.path.isfile(p):
                continue
            base, ext = os.path.splitext(os.path.basename(p))
            shutil.move(p, unique_path(TRASH_DIR, base, ext))
            deplacees.append(src)
        return {'ok': True, 'deplacees': deplacees}


def main():
    handler = partial(Admin, directory=ROOT)
    url = 'http://127.0.0.1:%d/admin' % PORT
    try:
        srv = ThreadingHTTPServer(('127.0.0.1', PORT), handler)
    except OSError:
        print("Impossible d'ouvrir le port %d — l'administration est peut-être déjà lancée." % PORT)
        if OPEN:
            webbrowser.open(url)
        sys.exit(1)
    print('SHOOTBYTHEO — administration locale')
    print('  Site  : http://127.0.0.1:%d/' % PORT)
    print('  Admin : %s' % url)
    print('  (fermez cette fenêtre ou Ctrl+C pour arrêter)')
    if OPEN:
        threading.Timer(0.8, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nArrêt.')


if __name__ == '__main__':
    main()
