# Configuration EmailJS pour le formulaire de contact

## 🚀 Configuration requise

Pour que le formulaire de contact fonctionne, vous devez configurer EmailJS :

### 1. Créer un compte EmailJS
- Allez sur [https://www.emailjs.com/](https://www.emailjs.com/)
- Créez un compte gratuit

### 2. Configuration des services
1. **Service Email** :
   - Dans votre dashboard EmailJS, allez dans "Email Services"
   - Ajoutez un service (Gmail, Outlook, etc.)
   - Notez l'ID du service (ex: `service_xxxxx`)

2. **Template d'email** :
   - Allez dans "Email Templates"
   - Créez un nouveau template avec ces variables :
     ```
     Nom: {{from_name}}
     Email: {{from_email}}
     Instagram: {{instagram}}
     Ville: {{ville}}
     Message: {{message}}
     ```
   - Notez l'ID du template (ex: `template_xxxxx`)

3. **Clé publique** :
   - Dans "Account" > "General", trouvez votre "Public Key"
   - Notez cette clé (ex: `xxxxxxxxxxxxxx`)

### 3. Modifier les fichiers

**Dans `contact.js` :**
```javascript
// Remplacez ces valeurs par vos vraies clés
emailjs.init("VOTRE_PUBLIC_KEY");

emailjs.send('VOTRE_SERVICE_ID', 'VOTRE_TEMPLATE_ID', templateParams)
```

**Exemple :**
```javascript
emailjs.init("abc123def456");
emailjs.send('service_gmail', 'template_contact', templateParams)
```

### 4. Configuration de l'email destinataire

Par défaut, les emails sont envoyés à `contact@shootbytheo.com`. Si vous voulez changer l'adresse, modifiez la ligne dans `contact.js` :
```javascript
to_email: 'votre@email.com'
```

## ✅ Test

Une fois configuré :
1. Ouvrez `contact.html` dans votre navigateur
2. Remplissez et envoyez le formulaire
3. Vérifiez que vous recevez l'email

## 🔧 Dépannage

- **Erreur "Invalid service ID"** : Vérifiez l'ID du service
- **Erreur "Invalid template ID"** : Vérifiez l'ID du template
- **Pas d'email reçu** : Vérifiez les spams et la configuration du service email

## 💡 Alternative gratuite

Si EmailJS ne convient pas, vous pouvez utiliser :
- **Formspree** (https://formspree.io/) - Plus simple à configurer
- **Netlify Forms** (si hébergé sur Netlify)

---

**Note** : EmailJS est gratuit pour jusqu'à 200 emails/mois.