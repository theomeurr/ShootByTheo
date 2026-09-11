/* Les données client ne sont jamais ajoutées au modèle public SITE_DATA. */
window.afficherLivraisons = function (container) {
  'use strict';
  const node = (tag, text, attrs = {}) => {
    const n = document.createElement(tag);
    if (text) n.textContent = text;
    Object.entries(attrs).forEach(([key, value]) => n.setAttribute(key, value));
    return n;
  };
  const message = node('p', '', {role: 'status', 'aria-live': 'polite'});
  const content = node('div');
  container.append(node('h1', 'Livraisons clients'),
    node('p', 'Créez une galerie, ajoutez vos originaux et préparez son dossier pour OVH.'), message, content);
  let galleries = [], selected = null, busy = false;
  async function request(path, body, raw = false) {
    const response = await fetch('/api/livraisons' + path, body === undefined ? {} : {
      method: 'POST', body: raw ? body : JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.erreur || 'La demande a échoué.');
    return data;
  }
  async function action(fn) {
    if (busy) return;
    busy = true;
    content.querySelectorAll('button,input').forEach(n => { n.disabled = true; });
    try { await fn(); } catch (error) { message.textContent = error.message; }
    finally {
      busy = false;
      content.querySelectorAll('button,input').forEach(n => { n.disabled = n.dataset.empty === 'true'; });
    }
  }
  const button = (text, fn) => {
    const b = node('button', text, {type: 'button', class: 'btn'});
    b.addEventListener('click', () => action(fn));
    return b;
  };
  function draw() {
    content.replaceChildren();
    if (!selected) {
      const form = node('form');
      const title = node('input', '', {placeholder: 'Ex. Mariage de Camille et Alex', maxlength: '200', required: '', id: 'titre-livraison'});
      form.append(node('label', 'Titre de la galerie', {for: 'titre-livraison'}), title);
      const create = node('button', 'Créer une livraison', {type: 'submit', class: 'btn'});
      form.append(create);
      form.addEventListener('submit', e => {
        e.preventDefault();
        action(async () => {
          selected = await request('/creer', {titre: title.value});
          galleries.unshift(selected); message.textContent = 'Galerie créée sur cet ordinateur.'; draw();
        });
      });
      content.append(form, node('h2', 'Vos livraisons'));
      if (!galleries.length) content.append(node('p', 'Aucune livraison pour le moment.'));
      galleries.forEach(gallery => content.append(button(gallery.titre + ' · ' + gallery.photos.length + ' photos', async () => {
        selected = gallery; message.textContent = ''; draw();
      })));
      return;
    }
    const gallery = selected;
    content.append(button('← Toutes les livraisons', async () => { selected = null; draw(); }),
      node('h2', gallery.titre), node('p', gallery.photos.length + ' photos · Fichiers originaux conservés sans réduction.'));
    const input = node('input', '', {type: 'file', multiple: '', accept: 'image/jpeg,image/png,image/webp', id: 'photos-livraison'});
    content.append(node('label', 'Ajouter des photos (JPEG, PNG ou WebP, 100 Mo maximum par photo)', {for: 'photos-livraison'}), input);
    input.addEventListener('change', () => {
      const files = Array.from(input.files);
      action(async () => {
        let done = 0;
        try {
          for (const file of files) {
            message.textContent = 'Importation ' + (done + 1) + ' / ' + files.length + ' — ' + file.name;
            if (file.size > 100 * 1024 * 1024) throw new Error(file.name + ' dépasse 100 Mo.');
            selected = await request('/photo?id=' + gallery.id + '&name=' + encodeURIComponent(file.name), file, true);
            galleries = galleries.map(g => g.id === selected.id ? selected : g);
            done++;
          }
          message.textContent = done + ' photos ajoutées.';
        } catch (error) {
          throw new Error(done + ' photos ajoutées. ' + error.message + ' Vous pouvez réimporter les fichiers restants.');
        } finally { draw(); }
      });
    });
    const prepare = button('Préparer la galerie et son export', async () => {
      message.textContent = 'Préparation des aperçus et des archives…';
      const result = await request('/preparer', {id: gallery.id});
      output.replaceChildren(node('h3', 'Prête à déposer sur OVH'),
        node('a', 'Ouvrir l’aperçu', {href: result.apercu, target: '_blank', rel: 'noopener', class: 'btn'}),
        node('a', 'Télécharger le dossier pour OVH ↓', {href: result.export, class: 'btn', download: ''}),
        node('p', 'Décompressez cet export, puis déposez son dossier « livraison » à la racine de votre site sur OVH, à côté de index.html. Le lien client fonctionnera après ce transfert.'));
      if (result.lien) {
        const link = node('input', '', {readonly: '', 'aria-label': 'Lien client après transfert sur OVH'});
        link.value = result.lien;
        output.append(link, button('Copier le lien client', async () => {
          try { await navigator.clipboard.writeText(result.lien); message.textContent = 'Lien copié. À envoyer après le transfert sur OVH.'; }
          catch (_) { link.focus(); link.select(); message.textContent = 'Sélectionnez puis copiez le lien affiché.'; }
        }));
      } else output.append(node('p', 'Pour obtenir le lien complet, renseignez l’adresse du site dans Réglages, puis préparez à nouveau la galerie.'));
      message.textContent = 'Export prêt. Il n’a pas encore été envoyé sur OVH.';
    });
    prepare.disabled = !gallery.photos.length;
    // L’état vide doit rester désactivé après la fin d’une autre action.
    prepare.dataset.empty = gallery.photos.length ? '' : 'true';
    const output = node('div');
    content.append(node('p', 'Ces livraisons restent hors du dépôt GitHub. Le bouton « Publier en ligne » du portfolio ne les transfère pas.'), prepare, output);
    const list = node('ul');
    gallery.photos.forEach(photo => list.append(node('li', photo.nom + ' · ' + (photo.octets / 1048576).toFixed(1) + ' Mo')));
    content.append(list);
  }
  action(async () => { galleries = await request(''); draw(); });
};
