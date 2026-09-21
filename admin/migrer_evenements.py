#!/usr/bin/env python3
"""Aplatit l'ancien modèle « séries → journées » en une liste d'événements.

    python3 admin/migrer_evenements.py [data.js]

Le site rangeait les photos en séries (Badminton, Judo), chacune découpée en
journées. Une série de plus n'apportait rien qu'un clic de plus : on ouvrait
Badminton pour y trouver ses journées, qui étaient le vrai sujet. Le sport
survit comme simple étiquette portée par l'événement.

  - chaque journée devient un événement, avec le sport de sa série ;
  - une série sans journée (Judo) devient un seul événement ;
  - « slides » disparaît : un événement porte « une », et le cadrage de sa
    couverture le suit ;
  - « travail: false » masquait une série de la liste sans la rendre privée.
    Ce réglage n'existe plus : l'événement devient privé, ce qui produit
    exactement la même visibilité, et se décoche en un clic.

Le script est sans effet sur un fichier déjà migré : il le dit et s'arrête.
"""
import json
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 3


def lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        brut = f.read()
    m = re.search(r'\{.*\}', brut, re.S)
    if not m:
        raise SystemExit('data.js : aucun objet JSON trouvé.')
    return json.loads(m.group(0))


def ecrire(chemin, d):
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write('window.SITE_DATA = ' + json.dumps(d, ensure_ascii=False, indent=2) + ';\n')


def migrer(d):
    # Les deux mises en avant de la page d'accueil désignaient déjà une journée.
    unes = {}
    for s in d.get('slides') or []:
        if s.get('album'):
            unes[s['album']] = s.get('pos', '')
        elif s.get('serie'):
            unes['serie:' + s['serie']] = s.get('pos', '')

    evenements = []
    for serie in d.get('series') or []:
        sport = (serie.get('title') or '').strip()
        cache = not serie.get('travail', True)
        photos = serie.get('photos') or []
        albums = serie.get('albums') or []

        if albums:
            for a in albums:
                aid = a.get('id') or ''
                evenements.append({
                    'id': aid,
                    'titre': a.get('titre') or '',
                    'sport': sport,
                    'date': a.get('date') or '',
                    'texte': '',
                    'cover': a.get('cover') or '',
                    'coverPos': unes.get(aid, ''),
                    'une': aid in unes,
                    'prive': bool(a.get('prive')) or cache,
                    'photos': [nettoyer(p) for p in photos if (p.get('album') or '') == aid],
                })
            # Une photo rangée dans aucune journée n'était visible nulle part ;
            # elle rejoint un événement à part plutôt que d'être perdue.
            orphelines = [p for p in photos if not (p.get('album') or '')]
            if orphelines:
                evenements.append({
                    'id': unique(serie.get('key') or 'serie', evenements),
                    'titre': serie.get('title') or 'Sans titre',
                    'sport': sport,
                    'date': '',
                    'texte': serie.get('kicker') or serie.get('blurb') or '',
                    'cover': serie.get('cover') or '',
                    'coverPos': '',
                    'une': False,
                    'prive': True,
                    'photos': [nettoyer(p) for p in orphelines],
                })
        else:
            cle = 'serie:' + (serie.get('key') or '')
            evenements.append({
                'id': unique(serie.get('key') or 'evenement', evenements),
                'titre': serie.get('title') or 'Sans titre',
                'sport': sport,
                'date': '',
                'texte': serie.get('kicker') or serie.get('blurb') or '',
                'cover': serie.get('cover') or '',
                'coverPos': unes.get(cle, ''),
                'une': cle in unes,
                'prive': bool(serie.get('prive')) or cache,
                'photos': [nettoyer(p) for p in photos],
            })

    evenements.sort(key=lambda e: (e['date'] or '0000', e['titre']), reverse=True)

    sortie = {'evenements': evenements}
    for cle in ('site', 'apropos', 'prestations'):
        if cle in d:
            sortie[cle] = d[cle]
    sortie['version'] = VERSION
    return sortie


def nettoyer(p):
    """Une photo n'a plus à dire à quelle journée elle appartient : elle y est."""
    return {k: v for k, v in p.items() if k != 'album'}


def unique(base, deja):
    vus = {e['id'] for e in deja}
    ident, n = base, 2
    while ident in vus:
        ident, n = '%s-%d' % (base, n), n + 1
    return ident


def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, 'data.js')
    d = lire(chemin)
    if 'evenements' in d and 'series' not in d:
        print('data.js est déjà au nouveau format : rien à faire.')
        return
    sortie = migrer(d)
    ecrire(chemin, sortie)

    print('%d événement(s) :' % len(sortie['evenements']))
    for e in sortie['evenements']:
        marques = ' '.join(filter(None, [
            '★ à la une' if e['une'] else '',
            'masqué' if e['prive'] else '',
            'sans date' if not e['date'] else '']))
        print('  %-28s %-11s %-11s %3d photo(s)  %s'
              % (e['id'][:28], e['sport'], e['date'] or '—', len(e['photos']), marques))


if __name__ == '__main__':
    main()
