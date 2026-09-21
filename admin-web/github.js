/* Administration en ligne — sans serveur.
 *
 * L'interface est celle du Mac, inchangée : elle appelle six routes par
 * fetch(). Ce fichier les intercepte et les sert depuis l'API GitHub, dans
 * le navigateur. Il n'y a donc rien à installer sur l'hébergeur, aucun
 * secret sur le serveur, et aucune page à défendre : sans jeton, cette page
 * ne sait rien faire.
 *
 * Le jeton reste dans le navigateur du photographe. Il se révoque d'un clic
 * sur GitHub si un appareil est perdu.
 */
(function () {
  'use strict';

  var DEPOT = window.SBT_DEPOT || 'theomeurr/ShootByTheo';
  var BRANCHE = window.SBT_BRANCHE || 'main';
  var CLE_JETON = 'sbt_jeton';
  var CLE_BROUILLON = 'sbt_brouillon';   // ancien brouillon, à oublier
  var BASE_BROUILLON = 'sbt-admin';      // IndexedDB : localStorage est trop petit
  var LARGEUR_MAX = 2000;      // mêmes réglages que le serveur local
  var QUALITE = 0.8;

  /* Les modifications s'accumulent ici et ne partent qu'au clic sur
     « Publier en ligne ». Sans cela, chaque frappe deviendrait une
     publication, donc un déploiement. */
  var attente = { data: null, fichiers: {}, suppressions: [] };
  // capturé avant toute interception, sinon gh() s'appellerait lui-même
  var vraiFetch = window.fetch.bind(window);
  var shaData = null;

  /* --------------------------------------------------------- brouillon
     Les photos envoyées ne sont pas encore sur GitHub : elles attendent en
     mémoire jusqu'au clic sur « Publier en ligne ». Seul data.js était
     conservé d'une ouverture à l'autre — un onglet rechargé, ou vidé par le
     téléphone, laissait donc un brouillon qui désignait des photos jamais
     envoyées, et la publication produisait des images manquantes. Les deux
     voyagent désormais ensemble, dans IndexedDB : localStorage plafonne à
     quelques mégaoctets, soit deux ou trois photos. */
  function base() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) return reject(new Error('sans IndexedDB'));
      var d = indexedDB.open(BASE_BROUILLON, 1);
      d.onupgradeneeded = function () {
        if (!d.result.objectStoreNames.contains('brouillon')) d.result.createObjectStore('brouillon');
      };
      d.onsuccess = function () { resolve(d.result); };
      d.onerror = function () { reject(d.error || new Error('base refusée')); };
    });
  }

  function surBase(mode, action) {
    return base().then(function (db) {
      return new Promise(function (resolve, reject) {
        var t = db.transaction('brouillon', mode);
        var r = action(t.objectStore('brouillon'));
        t.oncomplete = function () { resolve(r && r.result); };
        t.onerror = function () { reject(t.error); };
        t.onabort = function () { reject(t.error); };
      });
    });
  }

  /* Écrit au fil de l'eau, sans bloquer : perdre la dernière frappe est sans
     gravité, perdre les photos ne l'est pas. */
  function sauverBrouillon() {
    return surBase('readwrite', function (o) {
      return o.put({ data: attente.data, fichiers: attente.fichiers,
                     suppressions: attente.suppressions }, 'courant');
    }).catch(function () {});
  }
  function lireBrouillon() {
    return surBase('readonly', function (o) { return o.get('courant'); })
      .catch(function () { return null; });
  }
  function oublierBrouillon() {
    try { localStorage.removeItem(CLE_BROUILLON); } catch (e) {}
    return surBase('readwrite', function (o) { return o.delete('courant'); })
      .catch(function () {});
  }

  /* ------------------------------------------------------------- jeton */

  function jeton() {
    try { return localStorage.getItem(CLE_JETON) || ''; } catch (e) { return ''; }
  }
  function poserJeton(v) {
    try { v ? localStorage.setItem(CLE_JETON, v) : localStorage.removeItem(CLE_JETON); } catch (e) {}
    majBoutonCle();
  }

  /* Un seul écran à la fois : le démarrage de l'interface lance plusieurs
     appels d'affilée, et chacun en réclamerait un. Deux fenêtres
     superposées se bloquent mutuellement les clics. */
  var demandeEnCours = null;

  function demanderJeton(motif) {
    if (demandeEnCours) return demandeEnCours;
    demandeEnCours = new Promise(function (resolve) {
      var fond = document.createElement('div');
      fond.className = 'choix';
      fond.innerHTML =
        '<div class="boite" style="max-width:520px">' +
        '<h3 style="margin:0 0 6px">Connexion à GitHub</h3>' +
        '<p class="aide" id="sbtMotif"></p>' +
        '<label class="f" for="sbtJeton">Clé d’accès</label>' +
        '<input id="sbtJeton" type="password" placeholder="github_pat_…" autocomplete="off">' +
        '<div class="barre" style="margin-top:14px">' +
        '<button class="b" id="sbtOk">Se connecter</button>' +
        '<a class="b s" href="https://github.com/settings/personal-access-tokens" ' +
        'target="_blank" rel="noopener">Créer une clé ↗</a></div>' +
        '<p class="aide" style="margin-top:16px">La clé reste dans ce navigateur et ' +
        'n’est envoyée qu’à GitHub. Créez-la en accès <em>Only select repositories</em> ' +
        'sur ce dépôt, avec l’autorisation <em>Contents : Read and write</em>.</p>' +
        '</div>';
      document.body.appendChild(fond);
      fond.querySelector('#sbtMotif').textContent = motif;
      var champ = fond.querySelector('#sbtJeton');
      champ.focus();
      function valider() {
        var v = champ.value.trim();
        if (!v) { champ.focus(); return; }
        poserJeton(v);
        document.body.removeChild(fond);
        resolve(v);
      }
      fond.querySelector('#sbtOk').addEventListener('click', valider);
      champ.addEventListener('keydown', function (e) { if (e.key === 'Enter') valider(); });
    });
    demandeEnCours.then(function () { demandeEnCours = null; });
    return demandeEnCours;
  }

  /* ------------------------------------------------------------ GitHub */

  function gh(methode, chemin, corps) {
    var entetes = {
      'Accept': 'application/vnd.github+json',
      'Authorization': 'Bearer ' + jeton(),
      'X-GitHub-Api-Version': '2022-11-28'
    };
    var opts = { method: methode, headers: entetes };
    if (corps !== undefined) {
      entetes['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(corps);
    }
    // l'adresse est réglable pour pouvoir éprouver ces appels hors ligne
    var racine = window.SBT_GITHUB || 'https://api.github.com';
    return vraiFetch(racine + '/repos/' + DEPOT + chemin, opts)
      .then(function (r) {
        return r.text().then(function (t) {
          var d = t ? JSON.parse(t) : {};
          if (r.ok) return d;
          var e = new Error(messageGitHub(r.status, d));
          e.code = r.status;
          throw e;
        });
      });
  }

  function messageGitHub(code, d) {
    var m = (d && d.message) || '';
    if (code === 401) return 'JETON';
    if (code === 403 && /rate limit/i.test(m)) return 'GitHub limite les appels : réessayez dans un moment.';
    if (code === 403 || code === 404) {
      return 'Cette clé n’a pas le droit d’écrire sur ce dépôt, ou ne le voit pas. ' +
             'Vérifiez qu’elle vise « ' + DEPOT + ' » avec Contents : Read and write.';
    }
    if (code === 409 || /fast forward|not a fast/i.test(m)) {
      return 'Le contenu a changé ailleurs depuis l’ouverture de cette page. Rechargez avant de republier.';
    }
    return 'GitHub a répondu ' + code + (m ? ' : ' + m : '');
  }

  /* Réclame la clé si elle manque, la redemande si GitHub la refuse, et
     rejoue l'appel dans les deux cas. */
  function avecJeton(faire) {
    // la reprise est récursive : une clé refusée est redemandée autant de
    // fois qu'il le faut, sinon une faute de frappe condamnait l'appel.
    function tenter() {
      return faire().catch(function (e) {
        if (e.message !== 'JETON') throw e;
        poserJeton('');
        return demanderJeton('La clé a été refusée par GitHub. Elle a peut-être expiré.')
          .then(tenter);
      });
    }
    if (!jeton()) {
      return demanderJeton('Collez la clé GitHub qui autorise cette page à modifier le site.')
        .then(tenter);
    }
    return tenter();
  }

  function decode64(b64) {
    var bin = atob(b64.replace(/\n/g, ''));
    var o = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) o[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(o);
  }
  function encode64(texte) {
    var o = new TextEncoder().encode(texte), s = '';
    for (var i = 0; i < o.length; i++) s += String.fromCharCode(o[i]);
    return btoa(s);
  }
  function base64Blob(blob) {
    return new Promise(function (res, rej) {
      var fr = new FileReader();
      fr.onload = function () { res(String(fr.result).split(',')[1]); };
      fr.onerror = rej;
      fr.readAsDataURL(blob);
    });
  }

  /* ------------------------------------------------------------ photos */

  function slug(t) {
    return String(t).normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();
  }

  /* Réduction dans le navigateur : la photo part déjà au format web, ce qui
     évite d'envoyer 8 Mo par image depuis un téléphone en 4G. */
  async function reduire(fichier) {
    var bmp = await createImageBitmap(fichier, { imageOrientation: 'from-image' });
    var l = bmp.width, h = bmp.height;
    if (l > LARGEUR_MAX) { h = Math.round(h * LARGEUR_MAX / l); l = LARGEUR_MAX; }
    var c = document.createElement('canvas');
    c.width = l; c.height = h;
    var ctx = c.getContext('2d');
    ctx.fillStyle = '#fff';              // un PNG transparent virerait au noir
    ctx.fillRect(0, 0, l, h);
    ctx.drawImage(bmp, 0, 0, l, h);
    if (bmp.close) bmp.close();
    var blob = await new Promise(function (r) { c.toBlob(r, 'image/jpeg', QUALITE); });
    return { blob: blob, largeur: l, hauteur: h };
  }

  function cheminLibre(dossier, base, existants) {
    var c = dossier + '/' + base + '.jpg', n = 2;
    while (existants.indexOf(c) > -1 || attente.fichiers[c]) {
      c = dossier + '/' + base + '-' + n + '.jpg';
      n++;
    }
    return c;
  }

  /* Le contenu d'un dossier ne change pas tant qu'on n'a pas publié : le
     redemander à chaque photo faisait un aller-retour par photo, sur un
     listing qui grossit. Vingt photos, vingt appels — d'où la lenteur. */
  var listes = {};

  function listerDossier(dossier) {
    if (listes[dossier]) return Promise.resolve(listes[dossier].slice());
    return avecJeton(function () {
      return gh('GET', '/contents/' + dossier + '?ref=' + BRANCHE);
    }).then(function (l) {
      return (Array.isArray(l) ? l : []).filter(function (e) {
        return e.type === 'file' && /\.(jpe?g|png|webp)$/i.test(e.name);
      }).map(function (e) { return dossier + '/' + e.name; });
    }).then(function (l) { listes[dossier] = l; return l.slice(); })
      .catch(function () { listes[dossier] = []; return []; });   // dossier absent
  }

  /* ------------------------------------------------------- publication */

  function texteData(d) {
    return 'window.SITE_DATA = ' + JSON.stringify(d, null, 2) + ';\n';
  }

  async function publier() {
    var entrees = [];
    var ref = await avecJeton(function () { return gh('GET', '/git/ref/heads/' + BRANCHE); });
    var base = ref.object.sha;
    var commitBase = await gh('GET', '/git/commits/' + base);

    for (var chemin in attente.fichiers) {
      var blob = await gh('POST', '/git/blobs',
        { content: attente.fichiers[chemin], encoding: 'base64' });
      entrees.push({ path: chemin, mode: '100644', type: 'blob', sha: blob.sha });
    }
    if (attente.data) {
      var b = await gh('POST', '/git/blobs',
        { content: encode64(texteData(attente.data)), encoding: 'base64' });
      entrees.push({ path: 'data.js', mode: '100644', type: 'blob', sha: b.sha });
    }
    attente.suppressions.forEach(function (c) {
      entrees.push({ path: c, mode: '100644', type: 'blob', sha: null });
    });
    if (!entrees.length) return { ok: true, message: 'Tout est déjà en ligne', change: false };

    // Un seul commit pour l'ensemble : sans cela, vingt photos vaudraient
    // vingt publications, donc vingt déploiements à la file.
    var arbre = await gh('POST', '/git/trees', { base_tree: commitBase.tree.sha, tree: entrees });
    var horodatage = new Date().toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
    var commit = await gh('POST', '/git/commits', {
      message: 'Contenu du site — ' + horodatage + ' (en ligne)',
      tree: arbre.sha, parents: [base]
    });
    await gh('PATCH', '/git/refs/heads/' + BRANCHE, { sha: commit.sha });

    var n = entrees.length;
    attente = { data: null, fichiers: {}, suppressions: [] };
    listes = {};                      // le dépôt a changé : les listings aussi
    await oublierBrouillon();
    return { ok: true, change: true,
             message: n + ' modification' + (n > 1 ? 's' : '') + ' envoyée' + (n > 1 ? 's' : '') +
                      ' — le site sera à jour dans quelques minutes' };
  }

  function enAttente() {
    return Object.keys(attente.fichiers)
      .concat(attente.suppressions)
      .concat(attente.data ? ['data.js'] : []);
  }

  /* --------------------------------------------- interception des appels */

  var BASE = 'sbt-github:/';
  window.SBT_API = BASE;

  window.fetch = function (entree, opts) {
    var url = typeof entree === 'string' ? entree : (entree && entree.url) || '';
    if (url.indexOf(BASE) !== 0) return vraiFetch(entree, opts);
    return servir(url.slice(BASE.length), opts || {})
      .then(function (d) { return reponse(d, 200); })
      .catch(function (e) {
        return reponse({ erreur: e && e.message === 'JETON'
          ? 'Connexion à GitHub perdue. Rechargez la page.'
          : (e && e.message) || 'Échec de la demande.' }, 500);
      });
  };

  function reponse(obj, code) {
    return new Response(JSON.stringify(obj), {
      status: code, headers: { 'Content-Type': 'application/json' }
    });
  }

  async function servir(route, opts) {
    var q = {};
    var bout = route.split('?');
    (bout[1] || '').split('&').forEach(function (p) {
      if (!p) return;
      var kv = p.split('=');
      q[kv[0]] = decodeURIComponent(kv.slice(1).join('=') || '');
    });
    var nom = bout[0];
    var poste = (opts.method || 'GET').toUpperCase() === 'POST';

    if (nom === 'data' && !poste) {
      var f = await avecJeton(function () {
        return gh('GET', '/contents/data.js?ref=' + BRANCHE);
      });
      shaData = f.sha;
      var brut = decode64(f.content);
      var m = brut.match(/\{[\s\S]*\}/);
      var d = JSON.parse(m[0]);
      // un brouillon laissé par une page fermée trop tôt reprend la main,
      // photos comprises
      var br = await lireBrouillon();
      if (br && br.data) {
        attente.data = br.data;
        attente.fichiers = br.fichiers || {};
        attente.suppressions = br.suppressions || [];
        majBoutonCle();
        return attente.data;
      }
      return d;
    }

    if (nom === 'data' && poste) {
      attente.data = JSON.parse(opts.body);
      sauverBrouillon();
      return { ok: true };
    }

    if (nom === 'images') {
      var a = await listerDossier('image/accueil');
      var w = await listerDossier('image/web');
      Object.keys(attente.fichiers).forEach(function (c) {
        if (c.indexOf('image/accueil/') === 0) a.push(c);
        if (c.indexOf('image/web/') === 0) w.push(c);
      });
      return { accueil: a.sort(), web: w.sort() };
    }

    if (nom === 'upload') {
      var dossier = q.dossier === 'accueil' || q.dossier === 'apropos'
        ? 'image/' + q.dossier
        : 'image/galerie/' + (slug(q.evt || q.serie || 'galerie') || 'galerie');
      var reduit = await reduire(opts.body);
      var nomBase = slug((q.name || 'photo').replace(/\.[^.]+$/, '')) || 'photo';
      var chemin = cheminLibre(dossier, nomBase, await listerDossier(dossier));
      attente.fichiers[chemin] = await base64Blob(reduit.blob);
      await sauverBrouillon();
      return { src: chemin, largeur: reduit.largeur, hauteur: reduit.hauteur };
    }

    if (nom === 'trash') {
      var p = JSON.parse(opts.body || '{}');
      var srcs = p.srcs || (p.src ? [p.src] : []);
      srcs.forEach(function (s) {
        if (typeof s !== 'string' || s.indexOf('image/') !== 0 || s.indexOf('..') > -1) return;
        // une photo encore en attente n'a jamais atteint GitHub : on l'oublie
        if (attente.fichiers[s]) delete attente.fichiers[s];
        else if (attente.suppressions.indexOf(s) < 0) attente.suppressions.push(s);
      });
      await sauverBrouillon();
      return { ok: true, deplacees: srcs };
    }

    if (nom === 'git') {
      return { actif: true, branche: BRANCHE, fichiers: enAttente(), avance: 0 };
    }

    if (nom === 'publier') return publier();

    throw new Error('Requête inconnue : ' + nom);
  }

  /* ------------------------------------------------------- démarrage */

  window.addEventListener('beforeunload', function (e) {
    if (!enAttente().length) return;
    e.preventDefault();
    e.returnValue = '';
  });

  /* De quoi reprendre la main depuis l'appareil : la clé s'oublie ici, et se
     révoque sur GitHub si l'appareil est perdu. */
  var boutonCle = null;
  function majBoutonCle() {
    // la clé arrive après le chargement de la page : le bouton se pose une
    // fois pour toutes et suit son état.
    var tete = document.querySelector('header');
    if (!tete) return;
    if (!boutonCle) {
      boutonCle = document.createElement('button');
      boutonCle.className = 'b s p';
      boutonCle.textContent = 'Oublier la clé';
      boutonCle.title = 'Sur cet appareil seulement. Pour la désactiver partout, '
        + 'révoquez-la sur GitHub.';
      boutonCle.addEventListener('click', function () {
        if (enAttente().length &&
            !confirm('Des modifications ne sont pas encore publiées. Les perdre ?')) return;
        window.SBT_OUBLIER();
      });
      tete.insertBefore(boutonCle, document.getElementById('etat'));
    }
    boutonCle.hidden = !jeton();
  }
  document.addEventListener('DOMContentLoaded', majBoutonCle);

  /* Une photo envoyée n'est pas encore sur le serveur : son adresse ne répond
     donc pas, et l'administration n'affichait qu'un cadre vide — de quoi
     croire que l'import a échoué. Le fichier est là, en attente : on le montre
     tel quel jusqu'à la publication. */
  window.SBT_APERCU = function (chemin) {
    var b64 = attente.fichiers[chemin];
    return b64 ? 'data:image/jpeg;base64,' + b64 : '';
  };

  window.SBT_OUBLIER = function () {
    poserJeton('');
    oublierBrouillon().then(function () { location.reload(); });
  };
})();
