/* Livraisons clients, en ligne.
 *
 * Les originaux d'un client pèsent trop lourd pour Git : ils ne passent pas
 * par GitHub comme le reste de l'administration, mais montent directement chez
 * OVH, où quelques fichiers PHP les gardent hors de portée d'Apache.
 *
 * Ce fichier remplace la version locale de l'interface (livraisons-interface.js)
 * quand la page d'administration est servie par l'hébergeur.
 */
(function () {
  'use strict';

  var BASE = '/livraison/';
  var CLE = 'sbt_cle_livraisons';
  var LARGEUR_APERCU = 1600;
  var QUALITE = 0.82;

  var jeton = '';          // jeton de session, posé par « ouvrir »
  var maxOctets = 0;       // plus gros fichier accepté par l'hébergement
  var demandeEnCours = null;

  /** « 119 Mo », « 2,4 Mo », « 640 Ko » : un arrondi au mégaoctet afficherait
      « 0 Mo » chez un hébergeur serré. */
  function taille(o) {
    if (o >= 10485760) return Math.round(o / 1048576) + ' Mo';
    if (o >= 1048576) return (o / 1048576).toFixed(1).replace('.', ',') + ' Mo';
    return Math.max(1, Math.round(o / 1024)) + ' Ko';
  }

  function cle() {
    try { return localStorage.getItem(CLE) || ''; } catch (e) { return ''; }
  }
  function poserCle(v) {
    try { v ? localStorage.setItem(CLE, v) : localStorage.removeItem(CLE); } catch (e) {}
  }

  /* ---------------------------------------------------------- la clé */

  function demanderCle(motif) {
    if (demandeEnCours) return demandeEnCours;
    demandeEnCours = new Promise(function (resolve, rejeter) {
      var fond = document.createElement('div');
      fond.className = 'choix';
      fond.innerHTML =
        '<div class="boite" style="max-width:520px">' +
        '<h3 style="margin:0 0 6px">Clé des livraisons</h3>' +
        '<p class="aide" id="livMotif"></p>' +
        '<label class="f" for="livCle">Clé d’administration</label>' +
        '<input id="livCle" type="password" autocomplete="off">' +
        '<div class="barre" style="margin-top:14px">' +
        '<button class="b" id="livOk">Ouvrir</button>' +
        '<button class="b s" id="livNon">Annuler</button></div>' +
        '<p class="aide" style="margin-top:16px">Elle reste dans ce navigateur et ne ' +
        'protège que les livraisons. C’est la valeur du secret ' +
        '<em>OVH_CLE_LIVRAISONS</em> enregistré sur GitHub.</p></div>';
      document.body.appendChild(fond);
      fond.querySelector('#livMotif').textContent = motif;
      var champ = fond.querySelector('#livCle');
      champ.focus();
      function fermer() { if (fond.parentNode) document.body.removeChild(fond); }
      fond.querySelector('#livOk').addEventListener('click', function () {
        var v = champ.value.trim();
        if (!v) { champ.focus(); return; }
        poserCle(v); fermer(); resolve(v);
      });
      fond.querySelector('#livNon').addEventListener('click', function () {
        fermer(); rejeter(new Error('Clé non saisie.'));
      });
      champ.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') fond.querySelector('#livOk').click();
      });
    });
    demandeEnCours.catch(function () {}).then(function () { demandeEnCours = null; });
    return demandeEnCours;
  }

  /* --------------------------------------------------------- les appels */

  function brut(action, opts) {
    opts = opts || {};
    var url = BASE + 'api.php?a=' + action + (opts.l ? '&l=' + encodeURIComponent(opts.l) : '');
    var init = { method: opts.corps === undefined ? 'GET' : 'POST',
                 credentials: 'same-origin', headers: {}, cache: 'no-store' };
    if (jeton) init.headers['X-Jeton'] = jeton;
    if (opts.corps instanceof FormData) { init.body = opts.corps; }
    else if (opts.corps !== undefined) { init.body = JSON.stringify(opts.corps); }
    return fetch(url, init).then(function (r) {
      return r.json().catch(function () {
        throw new Error('L’hébergement a répondu ' + r.status + '. Les fichiers PHP des '
          + 'livraisons ne sont peut-être pas encore en ligne.');
      }).then(function (d) {
        if (!r.ok) { var e = new Error(d.erreur || 'La demande a échoué.'); e.code = r.status; throw e; }
        return d;
      });
    });
  }

  /* Une clé refusée ou une session expirée relancent la demande, une fois.
     Sans cela, la première erreur condamnerait la page jusqu'au rechargement. */
  function appel(action, opts, reessaye) {
    return brut(action, opts).catch(function (e) {
      if (e.code !== 401 || reessaye) throw e;
      return ouvrirSession(jeton ? 'Session expirée : ressaisissez la clé.'
                                 : 'Entrez la clé pour gérer les livraisons.')
        .then(function () { return appel(action, opts, true); });
    });
  }

  function ouvrirSession(motif) {
    var k = cle();
    var p = k ? Promise.resolve(k) : demanderCle(motif);
    return p.then(function (valeur) {
      return brut('ouvrir', { corps: { cle: valeur } }).catch(function (e) {
        poserCle('');                       // la clé gardée était fausse
        if (e.code === 401) { return demanderCle(e.message).then(function (v) {
          return brut('ouvrir', { corps: { cle: v } });
        }); }
        throw e;
      });
    }).then(function (d) {
      jeton = d.jeton; maxOctets = d.max_octets || 0;
      return d;
    });
  }

  /* ------------------------------------------------------------ aperçu */

  async function apercu(fichier) {
    var bmp = await createImageBitmap(fichier, { imageOrientation: 'from-image' });
    var l = bmp.width, h = bmp.height;
    var f = Math.min(1, LARGEUR_APERCU / Math.max(l, h));
    l = Math.max(1, Math.round(l * f));
    h = Math.max(1, Math.round(h * f));
    var c = document.createElement('canvas');
    c.width = l; c.height = h;
    var ctx = c.getContext('2d');
    ctx.fillStyle = '#fff';               // un PNG transparent virerait au noir
    ctx.fillRect(0, 0, l, h);
    ctx.drawImage(bmp, 0, 0, l, h);
    if (bmp.close) bmp.close();
    return new Promise(function (r) { c.toBlob(r, 'image/jpeg', QUALITE); });
  }

  /* ---------------------------------------------------------- l'écran */

  window.afficherLivraisons = function (conteneur) {
    var n = function (balise, texte, attrs) {
      var e = document.createElement(balise);
      if (texte) e.textContent = texte;
      Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
      return e;
    };
    var message = n('p', '', { role: 'status', 'aria-live': 'polite' });
    var corps = n('div');
    conteneur.append(
      n('h1', 'Livraisons clients'),
      n('p', 'Créez une galerie, envoyez vos originaux : le lien client marche aussitôt.',
        { class: 'sous' }),
      message, corps);

    var liste = [], ouverte = null, occupe = false;

    function agir(fn) {
      if (occupe) return Promise.resolve();
      occupe = true;
      corps.querySelectorAll('button,input').forEach(function (e) { e.disabled = true; });
      return Promise.resolve().then(fn).catch(function (e) {
        message.textContent = e && e.message ? e.message : 'La demande a échoué.';
      }).then(function () {
        occupe = false;
        corps.querySelectorAll('button,input').forEach(function (e) {
          e.disabled = e.dataset.vide === 'true';
        });
      });
    }
    var bouton = function (texte, fn, classe) {
      var b = n('button', texte, { type: 'button', class: classe || 'b' });
      b.addEventListener('click', function () { agir(fn); });
      return b;
    };
    function lien(id) { return location.origin + BASE + id + '/'; }

    function dessiner() {
      corps.replaceChildren();
      if (!ouverte) { dessinerListe(); } else { dessinerGalerie(); }
    }

    function dessinerListe() {
      var form = n('form');
      var titre = n('input', '', { type: 'text', maxlength: '200', required: '',
        id: 'liv-titre', placeholder: 'Ex. Mariage de Camille et Alex' });
      form.append(n('label', 'Titre de la galerie', { for: 'liv-titre', class: 'f' }), titre);
      var barre = n('div', '', { class: 'barre', style: 'margin-top:14px' });
      barre.append(n('button', 'Créer une livraison', { type: 'submit', class: 'b' }));
      form.append(barre);
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        agir(function () {
          return appel('creer', { corps: { titre: titre.value } }).then(function (d) {
            ouverte = d.livraison;
            message.textContent = 'Galerie créée. Son lien fonctionne déjà.';
            dessiner();
          });
        });
      });
      var bloc = n('div', '', { class: 'bloc' });
      bloc.append(n('h3', 'Nouvelle livraison'),
        n('p', 'Une galerie privée, en ligne dès sa création.', { class: 'aide' }), form);
      corps.append(bloc, n('h2', 'Vos livraisons', { style: 'font-size:16px;margin:24px 0 12px' }));
      if (!liste.length) { corps.append(n('p', 'Aucune livraison pour le moment.')); }
      liste.forEach(function (g) {
        corps.append(bouton((g.protege ? '🔒 ' : '') + g.titre + ' · ' + g.photos + ' photos',
          function () {
            return appel('galerie', { l: g.id }).then(function (d) {
              ouverte = d.livraison; message.textContent = ''; dessiner();
            });
          }, 'b s liv-item'));
      });
    }

    function dessinerGalerie() {
      var g = ouverte;
      corps.append(
        bouton('← Toutes les livraisons', function () {
          return appel('liste').then(function (d) {
            liste = d.livraisons; ouverte = null; message.textContent = ''; dessiner();
          });
        }, 'b s p'),
        n('h2', g.titre, { style: 'margin:16px 0 6px;font-size:22px;font-weight:800' }),
        n('p', g.photos.length + ' photos · originaux conservés sans réduction · '
          + (g.protege ? 'protégée par mot de passe' : 'accessible par lien seul'),
          { class: 'sous' }));

      /* -- le lien, seul élément que le client verra passer -- */
      var blocLien = n('div', '', { class: 'bloc' });
      var champ = n('input', '', { type: 'text', readonly: '', 'aria-label': 'Lien client' });
      champ.value = lien(g.id);
      var barreLien = n('div', '', { class: 'barre', style: 'margin-top:10px' });
      barreLien.append(
        bouton('Copier le lien client', function () {
          return navigator.clipboard.writeText(lien(g.id)).then(function () {
            message.textContent = 'Lien copié.';
          }, function () {
            champ.focus(); champ.select();
            message.textContent = 'Sélectionnez puis copiez le lien affiché.';
          });
        }),
        n('a', 'Ouvrir la galerie ↗', { href: lien(g.id), target: '_blank',
          rel: 'noopener', class: 'b s' }));
      blocLien.append(n('h3', 'Lien client'),
        n('p', 'À envoyer tel quel. Il reste le même tant que la galerie existe.',
          { class: 'aide' }), champ, barreLien);
      corps.append(blocLien);

      /* -- mot de passe -- */
      var blocMdp = n('div', '', { class: 'bloc' });
      blocMdp.append(n('h3', 'Mot de passe'),
        n('p', g.protege
          ? 'Cette galerie est protégée : le client saisit le mot de passe avant de voir les photos.'
          : 'Sans mot de passe, toute personne ayant le lien voit les photos.', { class: 'aide' }));
      var mdp = n('input', '', { type: 'password', id: 'liv-mdp', autocomplete: 'new-password',
        placeholder: g.protege ? 'Nouveau mot de passe' : 'Au moins 6 caractères' });
      blocMdp.append(n('label', g.protege ? 'Changer le mot de passe' : 'Protéger cette galerie',
        { for: 'liv-mdp', class: 'f' }), mdp);
      var barreMdp = n('div', '', { class: 'barre', style: 'margin-top:12px' });
      barreMdp.append(bouton(g.protege ? 'Changer le mot de passe' : 'Protéger la galerie',
        function () {
          return appel('mdp', { l: g.id, corps: { mdp: mdp.value } }).then(function (d) {
            ouverte = d.livraison;
            message.textContent = 'Mot de passe enregistré. Il s’applique tout de suite.';
            dessiner();
          });
        }));
      if (g.protege) {
        barreMdp.append(bouton('Retirer la protection', function () {
          if (!confirm('Retirer le mot de passe ? La galerie redeviendra accessible par son lien seul.')) return;
          return appel('mdp', { l: g.id, corps: { mdp: '' } }).then(function (d) {
            ouverte = d.livraison; message.textContent = 'Protection retirée.'; dessiner();
          });
        }, 'b d'));
      }
      blocMdp.append(barreMdp);
      corps.append(blocMdp);

      /* -- envoi des photos -- */
      var entree = n('input', '', { type: 'file', multiple: '', id: 'liv-photos',
        accept: 'image/jpeg,image/png,image/webp' });
      var blocEnvoi = n('div', '', { class: 'bloc' });
      blocEnvoi.append(n('h3', 'Ajouter des photos'),
        n('p', 'JPEG, PNG ou WebP' + (maxOctets
          ? ' · ' + taille(maxOctets) + ' maximum par photo, limite de l’hébergement.'
          : '.'), { class: 'aide' }),
        n('label', 'Choisir les fichiers', { for: 'liv-photos', class: 'f' }), entree);
      corps.append(blocEnvoi);
      entree.addEventListener('change', function () {
        var fichiers = Array.prototype.slice.call(entree.files);
        agir(function () { return envoyer(g, fichiers); });
      });

      /* -- photos déjà en ligne -- */
      if (g.photos.length) {
        var ul = n('ul', '', { class: 'liv-liste' });
        g.photos.forEach(function (p) {
          var li = n('li');
          var barre = n('div', '', { class: 'barre' });
          barre.append(n('span', p.nom + ' · ' + taille(p.octets), { style: 'flex:1' }));
          barre.append(bouton('Retirer', function () {
            if (!confirm('Retirer « ' + p.nom +' » de la galerie ?')) return;
            return appel('retirer', { l: g.id, corps: { photo: p.id } }).then(function (d) {
              ouverte = d.livraison; message.textContent = 'Photo retirée.'; dessiner();
            });
          }, 'b s p'));
          li.append(barre);
          ul.append(li);
        });
        var blocListe = n('div', '', { class: 'bloc' });
        blocListe.append(n('h3', 'Photos en ligne'), ul);
        corps.append(blocListe);
      }

      /* -- suppression -- */
      var blocFin = n('div', '', { class: 'bloc' });
      blocFin.append(n('h3', 'Retirer la livraison'),
        n('p', 'Supprime la galerie et ses photos de l’hébergement. Le lien cesse de répondre.',
          { class: 'aide' }),
        bouton('Supprimer définitivement', function () {
          if (!confirm('Supprimer « ' + g.titre + ' » et ses ' + g.photos.length
              + ' photos de l’hébergement ? Cette action est définitive.')) return;
          return appel('supprimer', { l: g.id, corps: {} }).then(function () {
            return appel('liste').then(function (d) {
              liste = d.livraisons; ouverte = null;
              message.textContent = 'Livraison supprimée.'; dessiner();
            });
          });
        }, 'b d'));
      corps.append(blocFin);
    }

    /* L'envoi est séquentiel : l'hébergement mutualisé n'aime pas dix
       transferts de 20 Mo à la fois, et une erreur reste lisible. */
    function envoyer(g, fichiers) {
      var faits = 0;
      function suivant() {
        if (faits >= fichiers.length) return Promise.resolve();
        var f = fichiers[faits];
        message.textContent = 'Envoi ' + (faits + 1) + ' / ' + fichiers.length + ' — ' + f.name;
        if (maxOctets && f.size > maxOctets) {
          return Promise.reject(new Error(f.name + ' dépasse la limite de '
            + taille(maxOctets) + ' de l’hébergement.'));
        }
        return apercu(f).catch(function () { return null; }).then(function (petit) {
          var fd = new FormData();
          fd.append('original', f, f.name);
          if (petit) fd.append('apercu', petit, 'apercu.jpg');
          fd.append('nom', f.name);
          return appel('photo', { l: g.id, corps: fd });
        }).then(function (d) {
          ouverte = d.livraison;
          faits++;
          return suivant();
        });
      }
      return suivant().then(function () {
        message.textContent = faits + ' photo(s) en ligne.';
      }, function (e) {
        throw new Error(faits + ' photo(s) envoyée(s). ' + (e && e.message ? e.message : '')
          + ' Vous pouvez reprendre avec les fichiers restants.');
      }).then(function () { dessiner(); }, function (e) { dessiner(); throw e; });
    }

    agir(function () {
      return brut('etat').then(function (d) {
        if (!d.configure) {
          throw new Error('Les livraisons en ligne ne sont pas encore configurées : '
            + 'ajoutez le secret OVH_CLE_LIVRAISONS sur GitHub, puis republiez le site.');
        }
        maxOctets = d.max_octets || 0;
        return appel('liste');
      }).then(function (d) { liste = d.livraisons; dessiner(); });
    });
  };
})();
