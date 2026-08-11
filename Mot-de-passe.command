#!/bin/bash
# Double-cliquez ici pour choisir le mot de passe de l'administration en ligne.
cd "$(dirname "$0")" || exit 1
/usr/bin/python3 admin/motdepasse.py
echo "Appuyez sur une touche pour fermer cette fenêtre."
read -r -n 1 -s
