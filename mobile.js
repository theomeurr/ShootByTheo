/* ============================================================
   SHOOTBYTHEO — accueil mobile

   Couche additive : elle lit window.SITE_DATA, comme le moteur
   du site, et n'écrit jamais dedans. En dessous de 700 px elle
   remplace le diaporama de l'accueil par un carrousel qu'on fait
   glisser, ajoute la liste des événements sous la photo à la une, et
   installe une barre d'onglets fixe en bas. Au-delà de 700 px
   elle démonte tout et le site desktop reprend la main.

   À charger dans index.html APRÈS data.js et après le script
   principal :
       <script src="data.js"></script>
       <script> … moteur du site … </script>
       <script src="mobile.js"></script>
   ============================================================ */
(function(){
  'use strict';

  var MQ = window.matchMedia('(max-width:700px)');
  var D       = window.SITE_DATA || {};
  var EVTS    = D.evenements || [];
  var PRESTA  = D.prestations || {};
  var APROPOS = D.apropos || {};
  var VIG     = D.vignettes || {};

  EVTS.forEach(function(e){ e.photos = e.photos || []; });

  function pad2(n){ return ('0' + n).slice(-2); }
  function petite(src){ return VIG[src] || src; }
  function couverture(e){
    return e ? (e.cover || (e.photos[0] && e.photos[0].src) || '') : '';
  }
  function evenementsPublics(){
    return EVTS.filter(function(e){ return !e.prive; });
  }
  /* Même règle que le moteur du site : rien de coché ne doit pas donner un
     accueil vide. */
  function unes(){
    var pubs = evenementsPublics();
    var choisis = pubs.filter(function(e){ return e.une && couverture(e); });
    return choisis.length ? choisis : pubs.filter(function(e){ return couverture(e); }).slice(0, 3);
  }
  var MOIS = ['janvier','février','mars','avril','mai','juin','juillet','août',
              'septembre','octobre','novembre','décembre'];
  function dateLisible(iso){
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    if (!m) return '';
    return parseInt(m[3], 10) + ' ' + MOIS[parseInt(m[2], 10) - 1] + ' ' + m[1];
  }
  function aller(route){ window.location.hash = '#/' + route; }

  var maison = null, onglets = null, lienHD = null;

  /* ---------- Accueil mobile ---------- */
  function construireAccueil(){
    var hote = document.getElementById('view-home');
    if (!hote || maison) return;

    maison = document.createElement('div');
    maison.className = 'mob-home';

    /* carrousel : une photo à la une par écran */
    var UNES = unes();
    var piste = document.createElement('div');
    piste.className = 'mob-slides';
    UNES.forEach(function(e){
      var nb = e.photos.length;
      var vue = document.createElement('div');
      vue.className = 'mob-slide';
      vue.style.backgroundImage = "url('" + couverture(e) + "')";
      vue.style.backgroundPosition = e.coverPos || 'center';
      vue.innerHTML = '<div class="veil"></div><div class="txt">' +
        '<div class="tag"></div><h1 class="t"></h1><div class="m"></div></div>';
      vue.querySelector('.tag').textContent = ['À la une', e.sport || ''].filter(Boolean).join(' · ');
      vue.querySelector('.t').textContent = e.titre || '';
      vue.querySelector('.m').textContent = [dateLisible(e.date),
        nb ? nb + (nb > 1 ? ' photos' : ' photo') : ''].filter(Boolean).join(' · ');
      piste.appendChild(vue);
    });
    maison.appendChild(piste);

    /* repères + compteur */
    var reperes = document.createElement('div');
    reperes.className = 'mob-dots';
    UNES.forEach(function(){ reperes.appendChild(document.createElement('i')); });
    var compteur = document.createElement('span');
    compteur.className = 'c';
    reperes.appendChild(compteur);
    maison.appendChild(reperes);

    var courant = 0;
    function majPosition(){
      var l = piste.clientWidth || 1;
      var i = Math.max(0, Math.min(UNES.length - 1, Math.round(piste.scrollLeft / l)));
      courant = i;
      [].forEach.call(reperes.querySelectorAll('i'), function(el, n){
        el.classList.toggle('is-on', n === i);
      });
      compteur.textContent = pad2(i + 1) + ' / ' + pad2(UNES.length);
    }
    var attente = null;
    piste.addEventListener('scroll', function(){
      clearTimeout(attente);
      attente = setTimeout(majPosition, 40);
    });
    majPosition();

    /* appel à l'action : ouvre la galerie de la photo affichée */
    var cta = document.createElement('button');
    cta.className = 'btn-accent mob-cta';
    cta.textContent = 'Voir la galerie →';
    cta.addEventListener('click', function(){
      var e = UNES[courant];
      if (e) aller('evenement/' + e.id);
    });
    var boite = document.createElement('div');
    boite.style.padding = '0 18px';
    boite.appendChild(cta);
    maison.appendChild(boite);

    /* les séries, sous la photo à la une */
    var pubs = evenementsPublics();
    var titre = document.createElement('div');
    titre.className = 'mob-lbl';
    titre.textContent = 'Événements · ' + pubs.length;
    maison.appendChild(titre);

    var liste = document.createElement('div');
    liste.className = 'mob-series';
    pubs.forEach(function(e, i){
      var nbP = e.photos.length;
      var couv = couverture(e);
      var carte = document.createElement('button');
      carte.className = 'mob-serie';
      carte.innerHTML = '<img loading="lazy"><div class="veil"></div><div class="txt">' +
        '<div class="k"></div><div class="n"></div><div class="tags"></div></div>';
      var im = carte.querySelector('img');
      if (couv){ im.src = petite(couv); im.alt = e.titre || ''; }
      else { im.remove(); }
      carte.querySelector('.k').textContent =
        [dateLisible(e.date), e.sport || ''].filter(Boolean).join(' · ') || pad2(i + 1);
      carte.querySelector('.n').textContent = e.titre || '';
      if (e.texte){
        var b = document.createElement('p');
        b.className = 'b';
        b.textContent = e.texte;
        carte.querySelector('.txt').insertBefore(b, carte.querySelector('.tags'));
      }
      var tags = carte.querySelector('.tags');
      var t2 = document.createElement('span');
      t2.className = 'tag';
      t2.textContent = nbP ? nbP + (nbP > 1 ? ' photos' : ' photo') : 'À venir';
      tags.appendChild(t2);
      carte.addEventListener('click', function(){ aller('evenement/' + e.id); });
      liste.appendChild(carte);
    });
    maison.appendChild(liste);

    hote.appendChild(maison);
    document.body.classList.add('mob-on');
  }

  /* ---------- Barre d'onglets ---------- */
  var ONGLETS = [
    { route:'home',        label:'À la une' },
    { route:'evenements',  label:'Événements' },
    { route:'prestations', label:'Presta',  si:function(){ return !!PRESTA.actif; } },
    { route:'a-propos',    label:'À propos',si:function(){ return !!APROPOS.actif; } },
    { route:'contact',     label:'Contact' }
  ];

  function construireOnglets(){
    if (onglets) return;
    var actifs = ONGLETS.filter(function(o){ return !o.si || o.si(); });
    onglets = document.createElement('nav');
    onglets.className = 'mob-tabs';
    onglets.style.gridTemplateColumns = 'repeat(' + actifs.length + ',1fr)';
    actifs.forEach(function(o){
      var b = document.createElement('button');
      b.className = 'mob-tab';
      b.dataset.route = o.route;
      b.textContent = o.label;
      b.addEventListener('click', function(){ aller(o.route); });
      onglets.appendChild(b);
    });
    document.body.appendChild(onglets);
    majOnglets();
  }

  function majOnglets(){
    if (!onglets) return;
    var route = (window.location.hash || '').replace(/^#\/?/, '').split('/')[0] || 'home';
    if (route === 'evenement' || route === 'serie') route = 'evenements';
    [].forEach.call(onglets.querySelectorAll('.mob-tab'), function(b){
      b.classList.toggle('is-on', b.dataset.route === route);
    });
  }

  /* ---------- Lien HD dans le header ---------- */
  function construireHD(){
    if (lienHD) return;
    var hdr = document.querySelector('.hdr');
    var url = (D.site || {}).lienHD;
    if (!hdr || !url) return;
    lienHD = document.createElement('a');
    lienHD.className = 'hdr-hd';
    lienHD.href = url;
    lienHD.target = '_blank';
    lienHD.rel = 'noopener';
    lienHD.textContent = 'HD ↓';
    hdr.appendChild(lienHD);
  }

  /* ---------- Montage / démontage ---------- */
  function demonter(){
    if (maison){ maison.remove(); maison = null; }
    if (onglets){ onglets.remove(); onglets = null; }
    if (lienHD){ lienHD.remove(); lienHD = null; }
    document.body.classList.remove('mob-on');
  }

  function appliquer(){
    if (MQ.matches){
      construireHD();
      construireAccueil();
      construireOnglets();
      majOnglets();
    } else {
      demonter();
    }
  }

  if (MQ.addEventListener) MQ.addEventListener('change', appliquer);
  else MQ.addListener(appliquer);
  window.addEventListener('hashchange', majOnglets);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', appliquer);
  else appliquer();
})();
