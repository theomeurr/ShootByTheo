# Configuration du formulaire de contact

## Configuration Formspree

Le formulaire de contact utilise Formspree pour envoyer les emails sans configuration JavaScript complexe.

### Étapes pour configurer :

1. **Allez sur [formspree.io](https://formspree.io)** et créez un compte gratuit
2. **Créez un nouveau formulaire** avec l'adresse email `contact@shootbytheo.com`
3. **Copiez l'endpoint du formulaire** (ça ressemble à `https://formspree.io/f/xxxxxxxx`)
4. **Remplacez l'endpoint dans contact.html** :
   - Cherchez cette ligne : `<form action="https://formspree.io/f/xpznqkgb" method="POST">`
   - Remplacez `xpznqkgb` par votre propre ID de formulaire

### Test du formulaire

Une fois configuré, testez le formulaire en :
1. Ouvrant contact.html dans votre navigateur
2. Remplissant et envoyant le formulaire
3. Vérifiant que vous recevez l'email à contact@shootbytheo.com

### Avantages de Formspree :
- ✅ Gratuit pour usage personnel
- ✅ Pas de configuration JavaScript
- ✅ Gestion automatique du spam
- ✅ Interface simple pour gérer les soumissions