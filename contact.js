// Configuration EmailJS pour le formulaire de contact
// Remplacez ces valeurs par vos vraies clés EmailJS

document.addEventListener('DOMContentLoaded', function() {
    // Initialisation EmailJS (remplacez par votre clé publique)
    emailjs.init("YOUR_PUBLIC_KEY");

    const contactForm = document.getElementById('contact-form');
    const statusMessage = document.getElementById('status-message');

    if (contactForm) {
        contactForm.addEventListener('submit', function(event) {
            event.preventDefault();

            // Afficher le message de statut
            statusMessage.style.display = 'block';
            statusMessage.textContent = 'Envoi en cours...';
            statusMessage.style.color = '#ffffff';

            // Récupérer les valeurs du formulaire
            const templateParams = {
                from_name: document.getElementById('nom').value,
                from_email: document.getElementById('email').value,
                instagram: document.getElementById('instagram').value,
                message: document.getElementById('message').value,
                ville: document.getElementById('ville').value,
                to_email: 'contact@shootbytheo.com'
            };

            // Envoi avec EmailJS (remplacez par vos IDs de service et template)
            emailjs.send('YOUR_SERVICE_ID', 'YOUR_TEMPLATE_ID', templateParams)
                .then(function(response) {
                    console.log('Email envoyé avec succès!', response);
                    statusMessage.textContent = 'Message envoyé avec succès !';
                    statusMessage.style.color = '#00ff00';
                    contactForm.reset();
                })
                .catch(function(error) {
                    console.error('Erreur lors de l\'envoi:', error);
                    statusMessage.textContent = 'Erreur lors de l\'envoi. Veuillez réessayer.';
                    statusMessage.style.color = '#ff0000';
                });
        });
    }
});