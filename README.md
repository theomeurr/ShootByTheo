# SHOOTBYTHEO — site portfolio

Site vitrine de photographie sportive et documentaire : judo, badminton, aviation.
Page unique, entièrement statique (HTML, CSS, JavaScript), sans base de données
ni serveur applicatif. Il s'héberge n'importe où, y compris sur un hébergement mutualisé.

## Utilisation au quotidien

**Allez sur `https://votre-site/admin/`**, depuis un téléphone ou un
ordinateur. Tout se modifie là, sans rien installer (voir
« Administration en ligne » plus bas).

Le même outil existe en local, et reste nécessaire pour les **livraisons
clients** :

- **macOS** — double-cliquez sur `Administration.command`
  (premier lancement : clic droit → *Ouvrir*, macOS met en quarantaine tout
  fichier téléchargé)
- **Windows** — double-cliquez sur `Administration.bat`

Dans les deux cas :

- **Page d'accueil** — les photos à la une, leur titre, leur cadrage
- **Séries** — Badminton, Judo… chacune contenant des **journées** datées
- **Journées** — une compétition, un match : photos, légendes, ordre, couverture
- **À propos / Prestations / Réglages** — les textes et informations du site

Les photos envoyées sont automatiquement redimensionnées pour le web.
Une suppression déplace le fichier dans `image/corbeille/` : rien n'est effacé.

`Publier.command` (macOS) et `Publier.bat` (Windows) préparent le dossier à
mettre en ligne à la main. Ce n'est plus nécessaire au quotidien : le bouton
**Publier en ligne ↑** s'en charge.

> Les livraisons clients vivent dans `_livraisons/`, hors de Git : elles
> restent **sur la machine qui les a créées**. Une livraison préparée sur le
> Mac n'apparaît pas sur le PC, et inversement. Le portfolio, lui, est partagé
> par GitHub et se retrouve à l'identique partout.

## Organisation des fichiers

| Chemin | Rôle |
|---|---|
| `index.html` | Le site entier : structure, styles et moteur d'affichage |
| `data.js` | Tout le contenu (séries, journées, photos, textes) — écrit par l'administration |
| `admin/serveur.py` | Serveur local de l'administration |
| `admin/interface.html` | Interface de l'administration |
| `admin/publier.py` | Génère le dossier à mettre en ligne |
| `admin-web/github.js` | Administration en ligne : remplace le serveur local par GitHub |
| `*.command` / `*.bat` | Lanceurs de l'administration locale — macOS et Windows |
| `image/web/` | Images de couverture optimisées |
| `image/galerie/<série>/` | Photos des galeries |
| `*.html` (racine) | Anciennes pages, converties en redirections à la publication |

## Livraisons clients par lien

Dans **Administration → Livraisons clients**, créez une livraison et importez
vos photos JPEG, PNG ou WebP (100 Mo maximum par fichier). Les originaux sont
conservés sans modification ; des aperçus de 1600 px sont créés séparément.
Chaque livraison possède une adresse aléatoire de 128 bits, stable entre exports.
Elle n'apparaît ni dans les menus ni dans le sitemap. Elle peut être protégée
par un mot de passe (voir plus bas) ; sans mot de passe, toute personne
possédant le lien consulte et télécharge la galerie.

Cliquez sur **Préparer la galerie et son export**, puis :

1. Ouvrez l'aperçu pour vérifier les images.
2. Téléchargez et décompressez le dossier pour OVH.
3. Avec votre outil de transfert, déposez le dossier `livraison/` à côté du
   `index.html` public sur OVH (dans `www/`, ou le sous-dossier de votre site).
4. Ouvrez le lien client pour vérifier le transfert, puis envoyez-le au client.

Renseignez l'adresse du site dans **Réglages** pour obtenir le lien complet.
Le client peut agrandir les images, naviguer au clavier, télécharger chaque
original ou récupérer toutes les photos dans une archive ZIP.

**L'export ne met pas la galerie en ligne automatiquement.** Le bouton
**Publier en ligne** du portfolio ne transfère pas les livraisons : il passe
par ce dépôt public. Métadonnées, liens, aperçus, originaux et exports sont
stockés uniquement dans `_livraisons/`, ignoré par Git. Sauvegardez ce dossier
sur un autre support. Un export conserve une copie des originaux et son
archive ZIP : comptez environ trois fois la taille des photos importées. Les
aperçus des exports précédents sont effacés à chaque nouvelle préparation,
pour que le disque ne grossisse pas d'une livraison entière à chaque export.

Pour ajouter des photos à une livraison existante, ouvrez-la, importez les
photos supplémentaires, préparez un nouvel export et transférez-le au même
endroit : le lien reste identique. Pour retirer une livraison en ligne,
supprimez son dossier `livraison/<identifiant>/` chez OVH. Supprimer seulement
une copie locale ne retire pas les fichiers déjà hébergés.

### Mot de passe

Chaque livraison peut être protégée par un mot de passe, posé dans sa fiche.
Seule son empreinte est conservée : le mot de passe lui-même n'est écrit nulle
part et ne peut pas être retrouvé. Après l'avoir posé ou retiré, **préparez à
nouveau l'export** et transférez-le : la protection ne s'applique qu'aux
fichiers déposés sur OVH.

Une galerie protégée n'est plus servie en fichiers statiques. Les photos
passent sous `prives/`, qu'Apache refuse de servir, et PHP ne les diffuse
qu'une fois le mot de passe donné — sans quoi l'adresse d'un original suffirait
à contourner la page. La galerie exige donc **PHP sur l'hébergement**, ce
qu'OVH mutualisé fournit. Trois essais manqués et l'attente s'allonge, de cinq
secondes à cinq minutes.

Communiquez le mot de passe séparément du lien, par un autre canal. Une galerie
sans mot de passe reste accessible à toute personne qui possède son adresse.

Les pages et fichiers portent une consigne de non-indexation et le listing
de dossier est désactivé sur Apache. Les galeries ne chargent aucun
outil d'analyse ni aucune ressource tierce.

Tests : `python3 -m unittest discover -s admin -p 'test_*.py'` (Pillow requis).

## Modèle de contenu du portfolio

```
Série (Badminton)
 └── Journée (TOP 12 — 9ᵉ journée, 28 mars 2026)
      └── Photos (source, légende, dimensions)
```

Une série sans journée affiche simplement toutes ses photos.
Une journée sans photo reste invisible sur le site.
Séries et journées peuvent être marquées **privées** : accessibles par leur lien,
absentes des menus et du sitemap — pratique pour une galerie réservée à un club.

## Publication

`Publier.command` produit un dossier complet contenant :

- une **vraie page par série et par journée** (`/serie/badminton/top-12-9e-journee/`),
  avec son titre, sa description et son aperçu de partage
- `sitemap.xml`, `robots.txt` et les données structurées pour les moteurs de recherche
- les redirections des anciennes adresses, pour ne casser aucun lien existant
- `.htaccess` : redirection vers l'adresse unique du site, compression, cache
- une **vignette de 800 px par photo**, servie dans les mosaïques et les cartes
  de journée — la visionneuse ouvre toujours l'original. Une page galerie passe
  ainsi de 2,6 à 0,6 Mo. Ces vignettes ne sont pas versionnées : elles se
  recalculent à chaque publication, et exigent Pillow. Sans lui la publication
  réussit quand même, mais sert les photos en pleine taille

Renseignez l'adresse du site dans **Administration → Réglages** avant la première
publication : sans elle, pas de sitemap ni d'aperçus de partage corrects.

## Mise en ligne automatique

Dans l'administration, le bouton **Publier en ligne ↑** met le site public à
jour. Enregistrer écrit sur votre Mac ; publier envoie le contenu sur GitHub,
qui régénère le site et le dépose chez OVH — comptez quelques minutes. Le
bouton indique « Tout est en ligne » quand il n'y a rien à envoyer, et reste
caché si le dossier n'est pas relié à GitHub. Seuls `data.js` et `image/` sont
publiés : le reste du dossier ne part jamais par mégarde.

Le même enchaînement se déclenche à chaque `git push` sur `main`
(`.github/workflows/publier.yml`). Le dépôt n'a lieu que si le dossier généré
est complet ; sinon le déploiement échoue et l'ancienne version reste en place.
Un déclenchement manuel est possible depuis l'onglet **Actions** de GitHub.

Trois secrets sont à créer dans **Settings → Secrets and variables → Actions**,
onglet *Secrets* :

| Secret | Où le trouver chez OVH |
|---|---|
| `OVH_FTP_SERVER` | Espace client → Hébergements → FTP-SSH (`ftp.clusterXXX.hosting.ovh.net`) |
| `OVH_FTP_USERNAME` | même page — l'identifiant du compte FTP |
| `OVH_FTP_PASSWORD` | défini à la création du compte FTP, réinitialisable depuis la même page |

Le transfert se fait en **SFTP** : l'hébergement mutualisé OVH ne gère pas le
FTPS, il refuse `AUTH TLS`. Deux réglages facultatifs, dans l'onglet
*Variables* (et non *Secrets*) :

| Variable | À définir si |
|---|---|
| `OVH_FTP_DIR` | le domaine pointe vers un sous-dossier plutôt que `www` — indiquez le chemin **relatif au dossier de connexion**, barre oblique finale comprise, par exemple `www/shootbytheo/`. Un chemin commençant par `/` désignerait la racine du serveur et échouerait en SFTP |
| `OVH_PROTOCOLE` | votre offre n'ouvre pas le SSH : mettez `ftp`. Les identifiants circulent alors en clair sur le réseau |

Rien n'est supprimé sur le serveur : les fichiers de l'ancien site restent
en place tant que vous ne les retirez pas vous-même par FTP.

## Mesure d'audience et consentement

Le site charge Google Tag Manager (conteneur `GTM-NPSPD3SW`), mais **seulement
après un accord explicite du visiteur**. Tant qu'il n'a pas répondu au bandeau,
aucune requête ne part chez Google : le conteneur n'est injecté qu'à
l'acceptation. Le refus est mémorisé six mois — la durée conseillée par la
CNIL — puis la question est reposée, et le lien « Cookies » du pied de page
permet de revenir sur son choix à tout moment.

Le site changeant de vue sans recharger la page, chaque navigation pousse un
événement `vue_virtuelle` portant l'adresse et le titre : sans lui, Tag Manager
ne compterait que la page d'arrivée. Créez dans GTM un déclencheur
« Événement personnalisé » de ce nom pour y brancher vos balises.

## Administration en ligne

**`https://votre-site/admin/`** — l'administration complète depuis n'importe
quel appareil : accueil, séries, journées, photos, textes, réglages. C'est la
même interface que sur le Mac.

La page est **entièrement statique**. Rien n'est installé sur l'hébergeur, il
n'y a ni PHP, ni mot de passe, ni fichier de configuration à protéger : sans
clé, elle ne sait rien faire. Elle parle directement à GitHub, qui régénère et
déploie le site comme d'habitude.

À la première visite sur un appareil, collez une clé GitHub *fine-grained*
limitée à ce dépôt, avec **Contents : Read and write**
(https://github.com/settings/personal-access-tokens). Elle reste dans ce
navigateur et n'est envoyée qu'à GitHub. Le bouton **Oublier la clé** l'efface
de l'appareil ; pour la désactiver partout — appareil perdu, par exemple —
révoquez-la sur GitHub, l'effacer localement ne suffit pas.

Les photos sont réduites **dans le navigateur** avant l'envoi : une photo de
8 Mo part en quelques centaines de kilooctets, ce qui rend l'envoi depuis un
téléphone en 4G supportable.

Les modifications s'accumulent et ne partent qu'au clic sur **Publier en ligne ↑**,
en une seule fois. Vingt photos font une publication, pas vingt. Tant que rien
n'est publié, quitter la page demande confirmation, et le texte en cours est
conservé pour la prochaine ouverture.

> `Administration.command` reste utile pour une seule chose : les **livraisons
> clients**, dont les photos ne passent pas par GitHub. Tout le reste se fait
> en ligne.
## Prérequis

L'administration **en ligne** ne demande rien : un navigateur suffit.

Pour l'administration locale et les livraisons clients :

- **macOS** — Python 3 est fourni avec les outils de développement Apple ;
  le premier lancement propose de les installer.
  ```
  python3 -m pip install --user Pillow
  ```
- **Windows** — installez Python depuis https://www.python.org/downloads/ en
  cochant **« Add python.exe to PATH »**. Le lanceur le cherche ensuite tout
  seul et vous le dit s'il ne le trouve pas.
  ```
  py -3 -m pip install --user Pillow
  ```

Pillow sert à réduire les photos. Sans elle, l'administration refuse les
envois et la publication sert les images en pleine taille.

## À noter

Les photos originales en pleine résolution ne sont pas versionnées ici
(voir `.gitignore`) : ce dépôt est public, et elles constituent la valeur
vendue par le lien de téléchargement HD. Pensez à les sauvegarder ailleurs.
