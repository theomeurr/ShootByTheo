#!/bin/bash
# Double-cliquez sur ce fichier pour lancer l'administration du site.
# (Premier lancement : clic droit > Ouvrir si macOS affiche un avertissement.)
cd "$(dirname "$0")" || exit 1

# /usr/bin/python3 est celui de macOS ; sur une machine ou Python a ete
# installe autrement, on prend celui du PATH.
PY=/usr/bin/python3
[ -x "$PY" ] || PY=$(command -v python3)
if [ -z "$PY" ]; then
  echo "Python 3 est introuvable. Installez-le depuis https://www.python.org/downloads/"
  read -r -n 1 -s
  exit 1
fi

exec "$PY" admin/serveur.py --open
