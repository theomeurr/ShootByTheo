#!/bin/bash
# Double-cliquez ici pour préparer le dossier à envoyer chez l'hébergeur.
# Il apparaîtra sur le Bureau : « shootbytheo_en_ligne ».
cd "$(dirname "$0")" || exit 1
/usr/bin/python3 admin/publier.py
echo "Appuyez sur une touche pour fermer cette fenêtre."
read -r -n 1 -s
