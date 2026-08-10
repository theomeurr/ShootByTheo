#!/bin/bash
# Double-cliquez sur ce fichier pour lancer l'administration du site.
# (Premier lancement : clic droit > Ouvrir si macOS affiche un avertissement.)
cd "$(dirname "$0")" || exit 1
exec /usr/bin/python3 admin/serveur.py --open
