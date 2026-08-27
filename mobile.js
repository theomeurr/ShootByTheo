/* ============================================================
   SHOOTBYTHEO — accueil mobile

   Couche additive : elle lit window.SITE_DATA, comme le moteur
   du site, et n'écrit jamais dedans. En dessous de 700 px elle
   remplace le diaporama de l'accueil par un carrousel qu'on fait
   glisser, ajoute la liste des séries sous la photo à la une, et
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
  var SERIES  = D.series || [];
  var SLIDES  = D.slides || [];
  var PRESTA  = D.prestations || {};
  var APROPOS = D.apropos || {};
  var VIG     = D.vignettes || {};

  var index = {};
  SERIES.forEach(function(s){
    s.albums = s.albums || [];
    s.photos = s.photos || [];
    index[s.key] = s;
  });

  function pad2(n){ return ('0' + n).slice(-2); }
  function petite(src){ return VIG[src] || src; }
  function photosDe(s, albumId){
    return s.photos.filter(function(p){ return (p.album || '') === albumId; });
  }
  function albumsRemplis(s){
    return s.albums.filter(function(a){ return !a.prive && photosDe(s, a.id).length; });
  }
  function albumDe(s, id){
    return s.albums.filter(function(a){ return a.id === id; })[0];
  }
  function couvertureAlbum(s, a){
    if (a && a.cover) return a.cover;
    var ph = photosDe(s, a ? a.id : '');
    return (ph[0] && ph[0].src) || s.cover || '';
  }
  function seriesPubliques(){
    return SERIES.filter(function(s){ return s.travail && !s.prive; });
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
    var piste = document.createElement('div');
    piste.className = 'mob-slides';
    SLIDES.forEach(function(sl){
      var s = index[sl.serie];
      var img = sl.img || (s ? couvertureAlbum(s, albumDe(s, sl.album || '')) : '');
      var nb = s ? photosDe(s, sl.album || '').length : 0;

      var vue = document.createElement('div');
      vue.className = 'mob-slide';
      vue.style.backgroundImage = "url('" + img + "')";
      vue.style.backgroundPosition = sl.pos || 'center';
      vue.innerHTML = '<div class="veil"></div><div class="txt">' +
        '<div class="tag"></div><h1 class="t"></h1><div class="m"></div></div>';
      vue.querySelector('.tag').textContent = sl.tag || '';
      vue.querySelector('.t').textContent = sl.title || '';
      vue.querySelector('.m').textContent = [sl.meta, nb ? nb + (nb > 1 ? ' photos' : ' photo') : '']
        .filter(Boolean).join(' · ');
      piste.appendChild(vue);
    });
    maison.appendChild(piste);

    /* repères + compteur */
    var reperes = document.createElement('div');
    reperes.className = 'mob-dots';
    SLIDES.forEach(function(){ reperes.appendChild(document.createElement('i')); });
    var compteur = document.createElement('span');
    compteur.className = 'c';
    reperes.appendChild(compteur);
    maison.appendChild(reperes);

    var courant = 0;
    function majPosition(){
      var l = piste.clientWidth || 1;
      var i = Math.max(0, Math.min(SLIDES.length - 1, Math.round(piste.scrollLeft / l)));
      courant = i;
      [].forEach.call(reperes.querySelectorAll('i'), function(el, n){
        el.classList.toggle('is-on', n === i);
      });
      compteur.textContent = pad2(i + 1) + ' / ' + pad2(SLIDES.length);
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
      var sl = SLIDES[courant];
      if (sl) aller('serie/' + sl.serie + (sl.album ? '/' + sl.album : ''));
    });
    var boite = document.createElement('div');
    boite.style.padding = '0 18px';
    boite.appendChild(cta);
    maison.appendChild(boite);

    /* les séries, sous la photo à la une */
    var pubs = seriesPubliques();
    var titre = document.createElement('div');
    titre.className = 'mob-lbl';
    titre.textContent = 'Le travail · ' + pubs.length + (pubs.length > 1 ? ' séries' : ' série');
    maison.appendChild(titre);

    var liste = document.createElement('div');
    liste.className = 'mob-series';
    pubs.forEach(function(s, i){
      var nbJ = albumsRemplis(s).length, nbP = s.photos.length;
      var carte = document.createElement('button');
      carte.className = 'mob-serie';
      carte.innerHTML = '<img loading="lazy"><div class="veil"></div><div class="txt">' +
        '<div class="k"></div><div class="n"></div><div class="tags"></div></div>';
      var im = carte.querySelector('img');
      im.src = petite(s.cover || couvertureAlbum(s, albumsRemplis(s)[0]));
      im.alt = s.title || '';
      carte.querySelector('.k').textContent = pad2(i + 1) + (s.kicker ? ' · ' + s.kicker : '');
      carte.querySelector('.n').textContent = s.title || '';
      if (s.blurb){
        var b = document.createElement('p');
        b.className = 'b';
        b.textContent = s.blurb;
        carte.querySelector('.txt').insertBefore(b, carte.querySelector('.tags'));
      }
      var tags = carte.querySelector('.tags');
      if (nbJ){
        var t1 = document.createElement('span');
        t1.className = 'tag';
        t1.textContent = nbJ + (nbJ > 1 ? ' journées' : ' journée');
        tags.appendChild(t1);
      }
      if (nbP){
        var t2 = document.createElement('span');
        t2.className = 'tag';
        t2.textContent = nbP + (nbP > 1 ? ' photos' : ' photo');
        tags.appendChild(t2);
      }
      carte.addEventListener('click', function(){ aller('serie/' + s.key); });
      liste.appendChild(carte);
    });
    maison.appendChild(liste);

    hote.appendChild(maison);
    document.body.classList.add('mob-on');
  }

  /* ---------- Barre d'onglets ---------- */
  var ONGLETS = [
    { route:'home',        label:'À la une' },
    { route:'travail',     label:'Travail' },
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
    if (route === 'serie') route = 'travail';
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
