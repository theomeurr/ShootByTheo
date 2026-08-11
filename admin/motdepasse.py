#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fabrique l'empreinte du mot de passe de l'administration en ligne.

Le mot de passe lui-même n'est ni affiché, ni enregistré, ni transmis :
seule son empreinte sort d'ici, et on ne peut pas remonter du second au
premier. C'est elle qui se colle dans le secret GitHub ADMIN_MDP_HASH.
"""
import getpass
import hashlib
import os
import sys

# Coût du calcul : assez élevé pour décourager les essais en masse, assez
# bas pour que la page de connexion réponde tout de suite.
TOURS = 210000


def empreinte(mdp: str) -> str:
    sel = os.urandom(16)
    h = hashlib.pbkdf2_hmac('sha256', mdp.encode('utf-8'), sel, TOURS)
    return 'pbkdf2$sha256$%d$%s$%s' % (TOURS, sel.hex(), h.hex())


def main():
    print()
    print('  SBT — mot de passe de l\'administration en ligne')
    print('  ' + '─' * 46)
    print()
    print('  Choisissez le mot de passe que vous taperez sur votre')
    print('  téléphone. Rien ne s\'affiche pendant la saisie, c\'est normal.')
    print()

    try:
        mdp = getpass.getpass('  Mot de passe : ')
        encore = getpass.getpass('  Répétez-le    : ')
    except (KeyboardInterrupt, EOFError):
        print('\n  Annulé.\n')
        sys.exit(1)

    if mdp != encore:
        print('\n  Les deux saisies sont différentes. Relancez.\n')
        sys.exit(1)
    if len(mdp) < 10:
        print('\n  Trop court : 10 caractères au minimum.')
        print('  Cette page sera exposée sur Internet.\n')
        sys.exit(1)

    print()
    print('  Collez la ligne ci-dessous dans le secret GitHub')
    print('  nommé ADMIN_MDP_HASH :')
    print()
    print('  ' + empreinte(mdp))
    print()
    print('  (Le mot de passe n\'apparaît nulle part : cette ligne ne')
    print('   permet pas de le retrouver.)')
    print()


if __name__ == '__main__':
    main()
