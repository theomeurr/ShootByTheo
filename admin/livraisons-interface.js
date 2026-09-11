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
  const button = (text, fn, classe = 'b') => {
    const b = node('button', text, {type: 'button', class: classe});
    b.addEventListener('click', () => action(fn));
    return b;
  };
  function draw() {
    content.replaceChildren();
    if (!selected) {
      const form = node('form');
      const title = node('input', '', {type: 'text', placeholder: 'Ex. Mariage de Camille et Alex', maxlength: '200', required: '', id: 'titre-livraison'});
      form.append(node('label', 'Titre de la galerie', {for: 'titre-livraison', class: 'f'}), title);
      const create = node('button', 'Créer une livraison', {type: 'submit', class: 'b'});
      const barre = node('div', '', {class: 'barre', style: 'margin-top:14px'});
      barre.append(create);
      form.append(barre);
      form.addEventListener('submit', e => {
        e.preventDefault();
        action(async () => {
          selected = await request('/creer', {titre: title.value});
          galleries.unshift(selected); message.textContent = 'Galerie créée sur cet ordinateur.'; draw();
        });
      });
      const bloc = node('div', '', {class: 'bloc'});
      bloc.append(node('h3', 'Nouvelle livraison'),
        node('p', 'Une galerie privée, accessible par son lien seul.', {class: 'aide'}), form);
      content.append(bloc, node('h2', 'Vos livraisons', {style: 'font-size:16px;margin:24px 0 12px'}));
      if (!galleries.length) content.append(node('p', 'Aucune livraison pour le moment.'));
      galleries.forEach(gallery => content.append(button(gallery.titre + ' · ' + gallery.photos.length + ' photos', async () => {
        selected = gallery; message.textContent = ''; draw();
      }, 'b s liv-item')));
      return;
    }
    const gallery = selected;
    content.append(button('← Toutes les livraisons', async () => { selected = null; draw(); }, 'b s p'),
      node('h2', gallery.titre, {style: 'margin:16px 0 6px;font-size:22px;font-weight:800'}),
      node('p', gallery.photos.length + ' photos · Fichiers originaux conservés sans réduction.', {class: 'sous'}));
    const input = node('input', '', {type: 'file', multiple: '', accept: 'image/jpeg,image/png,image/webp', id: 'photos-livraison'});
    const blocEnvoi = node('div', '', {class: 'bloc'});
    blocEnvoi.append(node('h3', 'Ajouter des photos'),
      node('p', 'JPEG, PNG ou WebP · 100 Mo maximum par photo.', {class: 'aide'}),
      node('label', 'Choisir les fichiers', {for: 'photos-livraison', class: 'f'}), input);
    content.append(blocEnvoi);
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
      const actions = node('div', '', {class: 'barre', style: 'margin:12px 0 14px'});
      actions.append(
        node('a', 'Ouvrir l’aperçu ↗', {href: result.apercu, target: '_blank', rel: 'noopener', class: 'b s'}),
        node('a', 'Télécharger le dossier pour OVH ↓', {href: result.export, class: 'b', download: ''}));
      output.style.display = '';
      output.replaceChildren(node('h3', 'Prête à déposer sur OVH'), actions,
        node('p', 'Décompressez cet export, puis déposez son dossier « livraison » à la racine de votre site sur OVH, à côté de index.html. Le lien client fonctionnera après ce transfert.',
             {class: 'aide'}));
      if (result.lien) {
        const link = node('input', '', {type: 'text', readonly: '', 'aria-label': 'Lien client après transfert sur OVH', style: 'margin-top:12px'});
        link.value = result.lien;
        const barreLien = node('div', '', {class: 'barre', style: 'margin-top:10px'});
        output.append(link, barreLien);
        barreLien.append(button('Copier le lien client', async () => {
          try { await navigator.clipboard.writeText(result.lien); message.textContent = 'Lien copié. À envoyer après le transfert sur OVH.'; }
          catch (_) { link.focus(); link.select(); message.textContent = 'Sélectionnez puis copiez le lien affiché.'; }
        }));
      } else output.append(node('p', 'Pour obtenir le lien complet, renseignez l’adresse du site dans Réglages, puis préparez à nouveau la galerie.'));
      message.textContent = 'Export prêt. Il n’a pas encore été envoyé sur OVH.';
    });
    prepare.disabled = !gallery.photos.length;
    // L’état vide doit rester désactivé après la fin d’une autre action.
    prepare.dataset.empty = gallery.photos.length ? '' : 'true';
    const output = node('div', '', {class: 'bloc', style: 'display:none'});
    const blocExport = node('div', '', {class: 'bloc'});
    blocExport.append(node('h3', 'Préparer le dossier pour OVH'),
      node('p', 'Ces livraisons restent hors du dépôt GitHub : le bouton « Publier en ligne » du portfolio ne les transfère pas.', {class: 'aide'}), prepare);
    content.append(blocExport, output);
    if (gallery.photos.length) {
      const list = node('ul', '', {class: 'liv-liste'});
      gallery.photos.forEach(photo => list.append(node('li', photo.nom + ' · ' + (photo.octets / 1048576).toFixed(1) + ' Mo')));
      const blocListe = node('div', '', {class: 'bloc'});
      blocListe.append(node('h3', 'Photos importées'), list);
      content.append(blocListe);
    }
  }
  action(async () => { galleries = await request(''); draw(); });
};
