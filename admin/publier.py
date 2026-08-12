#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prépare le dossier à envoyer chez l'hébergeur.

En plus de rassembler les fichiers publics, ce script génère :
  - une vraie page par série et par journée (adresses réelles, indexables)
  - les aperçus de partage propres à chaque page
  - sitemap.xml et robots.txt
  - les données structurées qui décrivent l'activité à Google

Usage : python3 admin/publier.py [dossier_de_sortie]
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse

ADMIN_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ADMIN_DIR)
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else \
    os.path.expanduser('~/Desktop/shootbytheo_en_ligne')

# data.js n'est pas copié tel quel : il est réécrit plus bas pour y joindre
# la table des vignettes produites à la publication.
FICHIERS = ['index.html']
DOSSIERS = [os.path.join('image', d) for d in ('web', 'galerie', 'accueil', 'apropos')]
IMAGES = [os.path.join('image', 'logo.png'), os.path.join('image', 'favicon.png')]

ALIAS = {
    'judo': 'serie/judo', 'aviation': 'serie/aviation', 'badminton': 'serie/badminton',
    'street': 'serie/street', 'top12': 'serie/badminton', 'n2': 'serie/badminton',
    'travail': 'travail', 'contact': 'contact', 'galerie': '', 'principale': '',
}

REDIR = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url=/{c}">
<link rel="canonical" href="/{c}"><title>SHOOTBYTHEO</title></head>
<body style="background:#0c0b0a;color:#f2efe9;font-family:Helvetica,Arial,sans-serif;padding:40px">
<p>Cette page a déménagé. <a href="/{c}" style="color:#e2543a">Continuer vers le site →</a></p>
<script>location.replace('/{c}');</script></body></html>
"""

# Règles Apache pour l'hébergement (OVH mutualisé et compatibles).
# Les photos portent un nom stable : on les met en cache un an. Les pages et
# data.js changent à chaque publication : cache court, sinon le visiteur
# garderait l'ancienne galerie plusieurs jours.
HTACCESS_BASE = """# Fichier généré par admin/publier.py — les modifications seront écrasées.

ErrorDocument 404 /index.html

<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css text/xml text/plain application/javascript application/xml image/svg+xml
</IfModule>

<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType image/jpeg "access plus 1 year"
  ExpiresByType image/png  "access plus 1 year"
  ExpiresByType image/webp "access plus 1 year"
  ExpiresByType text/css   "access plus 1 week"
  ExpiresByType application/javascript "access plus 1 hour"
  ExpiresByType text/html  "access plus 0 seconds"
</IfModule>

<IfModule mod_headers.c>
  Header set X-Content-Type-Options "nosniff"
  Header set Referrer-Policy "strict-origin-when-cross-origin"
</IfModule>
"""

# Une seule adresse doit répondre, celle des balises canonical : tout le reste
# y est redirigé. Les deux conditions HTTPS couvrent les hébergements qui
# terminent le TLS en amont (sinon, boucle de redirection).
HTACCESS_CANON = """
<IfModule mod_rewrite.c>
  RewriteEngine On

  RewriteCond %{{HTTPS}} !=on
  RewriteCond %{{HTTP:X-Forwarded-Proto}} !=https
  RewriteRule ^ https://{host}%{{REQUEST_URI}} [L,R=301]

  RewriteCond %{{HTTP_HOST}} !^{host_re}$ [NC]
  RewriteRule ^ https://{host}%{{REQUEST_URI}} [L,R=301]
</IfModule>
"""


def donnees():
    p = os.path.join(ROOT, 'data.js')
    if not os.path.isfile(p):
        return {}
    with open(p, encoding='utf-8') as f:
        m = re.search(r'\{.*\}', f.read(), re.S)
    return json.loads(m.group(0)) if m else {}


def photos_de(s, aid):
    return [p for p in s.get('photos', []) if (p.get('album') or '') == aid]


def copier(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


# ------------------------------------------------------------------ vignettes
# La mosaïque affiche les photos dans des colonnes de 320 à 500 px mais
# chargeait les fichiers de 2000 px : une série entière pesait plusieurs
# mégaoctets pour des images grandes comme une carte postale. On produit ici
# une version réduite, servie dans la mosaïque et dans les cartes de journée ;
# la visionneuse continue d'ouvrir la photo pleine taille.
#
# Ces vignettes ne sont pas versionnées : elles se recalculent à chaque
# publication à partir des originaux du dépôt. Rien à lancer à la main, et
# le dépôt ne double pas de volume.
LARGEUR_VIGNETTE = 800
QUALITE_VIGNETTE = 78


def chemin_vignette(src):
    d, nom = os.path.split(src)
    return '/'.join([d, 'vignettes', nom]) if d else os.path.join('vignettes', nom)


def fabriquer_vignettes(chemins, out):
    """Réduit chaque image citée. Renvoie la table source -> vignette."""
    try:
        from PIL import Image
    except ImportError:
        return {}, 0, "Pillow n'est pas installé : les photos seront servies " \
                      'en pleine taille (pages plus lourdes).'
    table, gagne = {}, 0
    for src in chemins:
        entree = os.path.join(out, src)
        if not os.path.isfile(entree):
            continue
        cible_rel = chemin_vignette(src)
        cible = os.path.join(out, cible_rel)
        try:
            with Image.open(entree) as im:
                if im.width <= LARGEUR_VIGNETTE:
                    continue          # déjà petite : la réduire ne gagnerait rien
                im = im.convert('RGB')
                h = round(im.height * LARGEUR_VIGNETTE / im.width)
                im = im.resize((LARGEUR_VIGNETTE, h), Image.LANCZOS)
                os.makedirs(os.path.dirname(cible), exist_ok=True)
                im.save(cible, 'JPEG', quality=QUALITE_VIGNETTE,
                        optimize=True, progressive=True)
        except Exception as e:      # une image illisible ne doit pas tout arrêter
            print('  ! vignette impossible pour %s (%s)' % (src, e))
            continue
        table[src] = cible_rel
        gagne += os.path.getsize(entree) - os.path.getsize(cible)
    return table, gagne, None


def abs_url(domaine, chemin):
    return (domaine.rstrip('/') + '/' + chemin.lstrip('/')) if domaine else chemin


def page(gabarit, domaine, route, titre, description, image, corps_noscript, indexable=True):
    """Construit une page réelle à partir d'index.html."""
    h = gabarit
    h = h.replace('<head>', '<head>\n<base href="/">', 1)
    h = re.sub(r'<title>.*?</title>', '<title>' + html.escape(titre) + '</title>', h, count=1, flags=re.S)
    h = re.sub(r'(<meta name="description" content=")[^"]*(">)',
               r'\g<1>' + html.escape(description, quote=True) + r'\g<2>', h, count=1)
    h = re.sub(r'(<meta property="og:title" content=")[^"]*(">)',
               r'\g<1>' + html.escape(titre, quote=True) + r'\g<2>', h, count=1)
    h = re.sub(r'(<meta property="og:description" content=")[^"]*(">)',
               r'\g<1>' + html.escape(description, quote=True) + r'\g<2>', h, count=1)
    h = re.sub(r'(<meta property="og:image" content=")[^"]*(">)',
               r'\g<1>' + html.escape(abs_url(domaine, image), quote=True) + r'\g<2>', h, count=1)
    tetes = []
    if domaine:
        tetes.append('<meta property="og:url" content="%s">' % html.escape(abs_url(domaine, route), quote=True))
        tetes.append('<link rel="canonical" href="%s">' % html.escape(abs_url(domaine, route), quote=True))
    if not indexable:
        tetes.append('<meta name="robots" content="noindex,follow">')
    if tetes:
        h = h.replace('</head>', '\n'.join(tetes) + '\n</head>', 1)
    if corps_noscript:
        h = h.replace('</main>', '</main>\n<noscript>\n' + corps_noscript + '\n</noscript>', 1)
    if route:
        h = h.replace('<script src="data.js"></script>',
                      '<script>window.__ROUTE__=%s;</script>\n<script src="data.js"></script>'
                      % json.dumps(route.strip('/')), 1)
    return h


def noscript_galerie(titre, texte, photos):
    out = ['<h1>%s</h1>' % html.escape(titre)]
    if texte:
        out.append('<p>%s</p>' % html.escape(texte))
    for p in photos:
        leg = p.get('legende') or titre
        out.append('<figure><img src="/%s" alt="%s"><figcaption>%s</figcaption></figure>'
                   % (html.escape(p['src'], quote=True), html.escape(leg, quote=True), html.escape(leg)))
    return '\n'.join(out)


def main():
    if not os.path.isfile(os.path.join(ROOT, 'index.html')):
        print('index.html introuvable — lancez ce script depuis le dossier du site.')
        sys.exit(1)

    d = donnees()
    site = d.get('site', {})
    domaine = (site.get('domaine') or '').strip().rstrip('/')
    # l'adresse peut être saisie sans « https:// » : les URL absolues des
    # aperçus de partage et du sitemap seraient alors invalides.
    if domaine and '//' not in domaine:
        domaine = 'https://' + domaine
    hote = urlparse(domaine).netloc if domaine else ''
    desc_site = site.get('description') or 'Photographie sportive et documentaire.'

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    n = 0
    for f in FICHIERS + IMAGES:
        src = os.path.join(ROOT, f)
        if os.path.isfile(src):
            copier(src, os.path.join(OUT, f))
            n += 1
        else:
            print('  ! manquant : %s' % f)
    for dd in DOSSIERS:
        src = os.path.join(ROOT, dd)
        if not os.path.isdir(src):
            continue
        for dirpath, _, files in os.walk(src):
            for name in files:
                if name.startswith('.') or name.startswith('._'):
                    continue
                p = os.path.join(dirpath, name)
                copier(p, os.path.join(OUT, os.path.relpath(p, ROOT)))
                n += 1

    # ---- vignettes, puis data.js qui les référence ----
    a_reduire = []
    for s in d.get('series', []):
        a_reduire += [p.get('src', '') for p in s.get('photos', [])]
        a_reduire += [a.get('cover', '') for a in s.get('albums', [])]
        a_reduire.append(s.get('cover', ''))
    vignettes, gagne, souci_vignettes = fabriquer_vignettes(
        sorted({c for c in a_reduire if c}), OUT)
    n += len(vignettes)
    d['vignettes'] = vignettes
    with open(os.path.join(OUT, 'data.js'), 'w', encoding='utf-8') as f:
        f.write('window.SITE_DATA = '
                + json.dumps(d, ensure_ascii=False, indent=2) + ';\n')
    n += 1

    # ---- administration en ligne ----
    # Elle est en PHP, donc servie par l'hébergeur ; le fichier de
    # configuration, lui, ne passe jamais par ici : il contient des secrets et
    # sera déposé hors de la racine web. L'interface est celle de
    # l'administration locale, servie telle quelle.
    src_admin = os.path.join(ROOT, 'admin-web')
    if os.path.isdir(src_admin):
        dest_admin = os.path.join(OUT, 'admin')
        os.makedirs(dest_admin, exist_ok=True)
        for name in sorted(os.listdir(src_admin)):
            if name in ('config.php', 'config-exemple.php') or name.startswith('._'):
                continue
            p = os.path.join(src_admin, name)
            if os.path.isfile(p):
                copier(p, os.path.join(dest_admin, name))
                n += 1
        iface = os.path.join(ROOT, 'admin', 'interface.html')
        if os.path.isfile(iface):
            copier(iface, os.path.join(dest_admin, 'interface.html'))
            n += 1

    with open(os.path.join(ROOT, 'index.html'), encoding='utf-8') as f:
        gabarit = f.read()

    # ---- page d'accueil : aperçu + données structurées ----
    couv_accueil = ''
    if d.get('slides'):
        couv_accueil = d['slides'][0].get('img', '')
    accueil = page(gabarit, domaine, '', 'SHOOTBYTHEO — Photographie sport & documentaire',
                   desc_site, couv_accueil or 'image/logo.png', '', True)
    fiche = {
        '@context': 'https://schema.org', '@type': 'ProfessionalService',
        'name': 'SHOOTBYTHEO', 'description': desc_site,
        'image': abs_url(domaine, couv_accueil) if domaine else couv_accueil,
        'email': site.get('email', ''),
        'knowsAbout': ['photographie sportive', 'reportage', 'photographie documentaire'],
    }
    if domaine:
        fiche['url'] = domaine
    if site.get('ville'):
        fiche['areaServed'] = site['ville']
        fiche['address'] = {'@type': 'PostalAddress', 'addressLocality': site['ville']}
    if site.get('instagram'):
        fiche['sameAs'] = [site['instagram']]
    accueil = accueil.replace('</head>',
                              '<script type="application/ld+json">%s</script>\n</head>'
                              % json.dumps(fiche, ensure_ascii=False), 1)
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(accueil)

    # ---- une page par série et par journée ----
    adresses = ['']
    pages = 0
    for s in d.get('series', []):
        pub_s = s.get('travail') and not s.get('prive')
        route = 'serie/%s/' % s['key']
        libres = photos_de(s, '')
        cont = noscript_galerie(s.get('title', ''), s.get('blurb', ''), libres)
        for a in s.get('albums', []):
            ph = photos_de(s, a['id'])
            if ph:
                cont += '\n<h2>%s</h2>' % html.escape(a['titre'])
                cont += '\n' + noscript_galerie(a['titre'], '', ph)
        h = page(gabarit, domaine, route,
                 '%s · SHOOTBYTHEO' % s.get('title', ''),
                 s.get('blurb') or desc_site,
                 s.get('cover') or couv_accueil, cont, pub_s)
        os.makedirs(os.path.join(OUT, 'serie', s['key']), exist_ok=True)
        with open(os.path.join(OUT, 'serie', s['key'], 'index.html'), 'w', encoding='utf-8') as f:
            f.write(h)
        pages += 1
        if pub_s:
            adresses.append(route)

        for a in s.get('albums', []):
            ph = photos_de(s, a['id'])
            if not ph:
                continue
            r2 = 'serie/%s/%s/' % (s['key'], a['id'])
            pub_a = pub_s and not a.get('prive')
            titre = '%s · %s' % (a['titre'], s.get('title', ''))
            desc = '%s — %d photo%s%s.' % (a['titre'], len(ph), 's' if len(ph) > 1 else '',
                                           (' · ' + a['date']) if a.get('date') else '')
            h2 = page(gabarit, domaine, r2, titre + ' · SHOOTBYTHEO', desc,
                      a.get('cover') or ph[0]['src'],
                      noscript_galerie(a['titre'], s.get('title', ''), ph), pub_a)
            os.makedirs(os.path.join(OUT, 'serie', s['key'], a['id']), exist_ok=True)
            with open(os.path.join(OUT, 'serie', s['key'], a['id'], 'index.html'), 'w', encoding='utf-8') as f:
                f.write(h2)
            pages += 1
            if pub_a:
                adresses.append(r2)

    # ---- pages fixes ----
    for route, titre, desc, actif in (
        ('travail/', 'Le Travail · SHOOTBYTHEO', 'Les séries photographiques : ' +
         ', '.join(s.get('title', '') for s in d.get('series', []) if s.get('travail')), True),
        ('contact/', 'Contact · SHOOTBYTHEO', 'Prestation, reportage sportif, collaboration — écrivez-moi.', True),
        ('a-propos/', (d.get('apropos', {}).get('titre') or 'À propos') + ' · SHOOTBYTHEO',
         (d.get('apropos', {}).get('texte') or '')[:180], d.get('apropos', {}).get('actif')),
        ('prestations/', (d.get('prestations', {}).get('titre') or 'Prestations') + ' · SHOOTBYTHEO',
         d.get('prestations', {}).get('intro') or '', d.get('prestations', {}).get('actif')),
    ):
        if not actif:
            continue
        h = page(gabarit, domaine, route, titre, desc or desc_site, couv_accueil, '', True)
        os.makedirs(os.path.join(OUT, route.strip('/')), exist_ok=True)
        with open(os.path.join(OUT, route.strip('/'), 'index.html'), 'w', encoding='utf-8') as f:
            f.write(h)
        pages += 1
        adresses.append(route)

    # ---- anciennes adresses ----
    # ALIAS garde les séries d'hier (aviation, street…) : si l'une d'elles n'est
    # plus publiée, son ancienne adresse pointerait vers une page inexistante.
    # On renvoie alors vers « Le Travail » plutôt que vers un 404.
    publiees = {s['key'] for s in d.get('series', [])
                if s.get('travail') and not s.get('prive')}

    def cible_valide(c):
        if c.startswith('serie/') and c.split('/')[1] not in publiees:
            return 'travail'
        return c

    redirections = 0
    perdues = []
    for name in sorted(os.listdir(ROOT)):
        if not name.endswith('.html') or name in ('index.html', 'ancien-index.html') or name.startswith('.'):
            continue
        base = os.path.splitext(name)[0].lower()
        cible = ALIAS.get(base, '')
        if not cible:
            for cle, r in ALIAS.items():
                if re.search(r'(^|-)' + re.escape(cle) + r'(-|$)', base):
                    cible = r
                    break
        retenue = cible_valide(cible)
        if retenue != cible:
            perdues.append(name)
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write(REDIR.format(c=(retenue + '/') if retenue else ''))
        redirections += 1

    # ---- sitemap + robots ----
    if domaine:
        lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for a in adresses:
            lignes.append('  <url><loc>%s</loc></url>' % html.escape(abs_url(domaine, a), quote=True))
        lignes.append('</urlset>')
        with open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(lignes) + '\n')
        robots = 'User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n' % domaine
    else:
        robots = 'User-agent: *\nAllow: /\n'
    with open(os.path.join(OUT, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write(robots)

    # ---- règles serveur ----
    htaccess = HTACCESS_BASE
    if hote:
        htaccess += HTACCESS_CANON.format(host=hote, host_re=re.escape(hote))
    with open(os.path.join(OUT, '.htaccess'), 'w', encoding='utf-8') as f:
        f.write(htaccess)

    # ---- contrôles ----
    manquantes = []
    refs = [sl.get('img', '') for sl in d.get('slides', [])]
    for s in d.get('series', []):
        refs.append(s.get('cover', ''))
        refs += [p.get('src', '') for p in s.get('photos', [])]
        refs += [a.get('cover', '') for a in s.get('albums', [])]
    if d.get('apropos', {}).get('photo'):
        refs.append(d['apropos']['photo'])
    for c in refs:
        if c and not os.path.isfile(os.path.join(OUT, c)):
            manquantes.append(c)

    taille = sum(os.path.getsize(os.path.join(dp, f))
                 for dp, _, fs in os.walk(OUT) for f in fs)

    print('\nDossier prêt à mettre en ligne :')
    print('  %s' % OUT)
    print('  %d fichiers · %.1f Mo' % (n + pages + redirections, taille / 1e6))
    print('  %d page(s) générée(s) · %d redirection(s) d\'anciennes adresses' % (pages, redirections))
    if domaine:
        print('  sitemap.xml : %d adresse(s)' % len(adresses))
    else:
        print("  ⚠ Adresse du site non renseignée (Administration → Réglages) :")
        print("    pas de sitemap, et les aperçus de partage resteront incomplets.")
    if souci_vignettes:
        print('\n  ⚠ %s' % souci_vignettes)
    elif vignettes:
        print('  %d vignette(s) · %.1f Mo économisés au chargement des galeries'
              % (len(vignettes), gagne / 1e6))
    if perdues:
        print('\n  ℹ %d ancienne(s) adresse(s) sans série correspondante,' % len(perdues))
        print('    redirigée(s) vers « Le Travail » : %s' % ', '.join(perdues))
    if manquantes:
        print('\n  ⚠ Images introuvables :')
        for m in sorted(set(manquantes)):
            print('     - %s' % m)
    print('\nGlissez ce dossier chez votre hébergeur pour remplacer l\'ancien site.')
    print('(admin/, Administration.command et la corbeille en sont exclus.)\n')

    if sys.platform == 'darwin':
        subprocess.run(['open', OUT], check=False)


if __name__ == '__main__':
    main()
