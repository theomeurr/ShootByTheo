# SHOOTBYTHEO — site portfolio

Site vitrine de photographie sportive et documentaire : judo, badminton, aviation.
Page unique, entièrement statique (HTML, CSS, JavaScript), sans base de données
ni serveur applicatif. Il s'héberge n'importe où, y compris sur un hébergement mutualisé.

## Utilisation au quotidien

**Allez sur `https://votre-site/admin/`**, depuis un téléphone ou un
ordinateur. Tout se modifie là, sans rien installer (voir
« Administration en ligne » plus bas).

Le même outil existe en local, si vous préférez travailler depuis la machine
où sont vos photos :

- **macOS** — double-cliquez sur `Administration.command`
  (premier lancement : clic droit → *Ouvrir*, macOS met en quarantaine tout
  fichier téléchargé)
- **Windows** — double-cliquez sur `Administration.bat`

Dans les deux cas :

- **Événements** — une compétition, un match, une séance : photos, légendes,
  ordre, couverture. C'est le seul niveau : vous ouvrez l'événement, vous y
  déposez vos photos
- **À la une** — vous cochez les événements à afficher en grand sur la page
  d'accueil. Leur photo, leur titre et leur date sont repris tels quels
- **À propos / Prestations / Réglages** — les textes et informations du site

Les photos envoyées sont automatiquement redimensionnées pour le web.
Une suppression déplace le fichier dans `image/corbeille/` : rien n'est effacé.

`Publier.command` (macOS) et `Publier.bat` (Windows) préparent le dossier à
mettre en ligne à la main. Ce n'est plus nécessaire au quotidien : le bouton
**Publier en ligne ↑** s'en charge.

> **Deux chemins pour les livraisons clients.** En ligne, elles montent
> directement chez OVH et le lien client marche aussitôt, depuis n'importe quel
> appareil. En local, elles vivent dans `_livraisons/` — hors de Git, donc
> **sur la machine qui les a créées** — et demandent un transfert manuel. Une
> livraison faite en ligne se gère en ligne ; une livraison faite sur le Mac se
> gère sur le Mac. Le portfolio, lui, est partagé par GitHub et se retrouve à
> l'identique partout.

## Organisation des fichiers

| Chemin | Rôle |
|---|---|
| `index.html` | Le site entier : structure, styles et moteur d'affichage |
| `data.js` | Tout le contenu (événements, photos, textes) — écrit par l'administration |
| `admin/serveur.py` | Serveur local de l'administration |
| `admin/interface.html` | Interface de l'administration |
| `admin/publier.py` | Génère le dossier à mettre en ligne |
| `admin/migrer_evenements.py` | Aplatit l'ancien rangement séries → journées (à ne lancer qu'une fois) |
| `admin-web/github.js` | Administration en ligne : remplace le serveur local par GitHub |
| `admin-web/livraisons.js` | Livraisons clients en ligne, côté navigateur |
| `admin-web/livraison/` | Les quelques fichiers PHP déposés chez OVH pour les galeries clients |
| `*.command` / `*.bat` | Lanceurs de l'administration locale — macOS et Windows |
| `image/web/` | Images de couverture optimisées |
| `image/galerie/<événement>/` | Photos des galeries |
| `*.html` (racine) | Anciennes pages, converties en redirections à la publication |

## Livraisons clients par lien

Une livraison est une galerie privée : une adresse aléatoire de 128 bits, une
mosaïque, une visionneuse au clavier, le téléchargement d'un original ou de
toute la série en ZIP. Elle n'apparaît ni dans les menus, ni dans le sitemap,
ni dans `robots.txt`, et ne charge aucune ressource tierce.

### En ligne — le chemin normal

Dans **`https://votre-site/admin/` → Livraisons clients**, créez la galerie,
choisissez vos photos : elles montent directement chez OVH et **le lien client
fonctionne aussitôt**. Rien à préparer, rien à transférer, rien à décompresser.
Copiez le lien, envoyez-le.

Les originaux sont conservés sans aucune modification. L'aperçu de 1600 px est
fabriqué **dans le navigateur** avant l'envoi, pour que l'hébergement mutualisé
n'ait pas à redimensionner un fichier de 40 Mo. Les photos partent une par une :
une erreur reste lisible et le reste de l'envoi se reprend.

Par la suite, la même fiche permet d'ajouter des photos, d'en retirer une, de
poser ou de changer le mot de passe, et de supprimer la livraison de
l'hébergement. Tout s'applique immédiatement.

> **La taille maximale d'une photo est celle de l'hébergement**, pas la vôtre :
> l'écran d'envoi l'affiche (`upload_max_filesize` de PHP, 128 Mo chez OVH par
> défaut). Une photo au-delà est refusée avec la limite en clair.

#### Mise en route, une seule fois

Créez un secret `OVH_CLE_LIVRAISONS` dans **Settings → Secrets and variables →
Actions** : une phrase longue, choisie par vous. À la publication suivante,
seule son **empreinte** part chez OVH, dans un fichier placé *hors de la racine
web* — même servi en clair, il ne livrerait pas la clé.

Cette clé s'entre une fois par appareil, dans l'administration, et y reste.
Elle n'ouvre que les livraisons : elle ne donne accès ni au dépôt GitHub ni au
reste du site. Sans ce secret, la rubrique le dit et reste inactive.

### En local — l'export à transférer soi-même

`Administration.command` (macOS) et `Administration.bat` (Windows) gardent la
version locale, utile sans connexion. Les livraisons y vivent dans
`_livraisons/`, ignoré par Git. Cliquez sur **Préparer la galerie et son
export**, puis :

1. Ouvrez l'aperçu pour vérifier les images.
2. Téléchargez et décompressez le dossier pour OVH.
3. Avec votre outil de transfert, déposez le dossier `livraison/` à côté du
   `index.html` public sur OVH (dans `www/`, ou le sous-dossier de votre site).
4. Ouvrez le lien client pour vérifier le transfert, puis envoyez-le au client.

Renseignez l'adresse du site dans **Réglages** pour obtenir le lien complet.
Le bouton **Publier en ligne** du portfolio ne transfère pas ces exports : il
passe par ce dépôt public, où les photos des clients n'ont rien à faire.
Sauvegardez `_livraisons/` sur un autre support. Un export conserve une copie
des originaux et son archive ZIP : comptez environ trois fois la taille des
photos importées. Les aperçus des exports précédents sont effacés à chaque
nouvelle préparation, pour que le disque ne grossisse pas d'une livraison
entière à chaque export.

Pour ajouter des photos à une livraison locale déjà transférée, ouvrez-la,
importez les photos supplémentaires, préparez un nouvel export et transférez-le
au même endroit : le lien reste identique. Pour la retirer, supprimez son
dossier `livraison/<identifiant>/` chez OVH — effacer la copie locale ne retire
rien de l'hébergement.

### Mot de passe

Chaque livraison peut être protégée par un mot de passe, posé dans sa fiche.
Seule son empreinte est conservée : le mot de passe lui-même n'est écrit nulle
part et ne peut pas être retrouvé. En ligne, la protection s'applique tout de
suite ; en local, **préparez à nouveau l'export** et transférez-le, sans quoi
elle ne concerne que votre machine.

Une galerie protégée n'est plus servie en fichiers statiques. Les photos
passent sous `prives/`, qu'Apache refuse de servir, et PHP ne les diffuse
qu'une fois le mot de passe donné — sans quoi l'adresse d'un original suffirait
à contourner la page. Trois essais manqués et l'attente s'allonge, de cinq
secondes à cinq minutes.

Communiquez le mot de passe séparément du lien, par un autre canal. Une galerie
sans mot de passe reste accessible à toute personne qui possède son adresse.

### Ce qui est déposé chez OVH

Les livraisons demandent **PHP sur l'hébergement**, ce qu'OVH mutualisé
fournit. Un seul jeu de fichiers sert toutes les galeries :

```
www/livraison/
  .htaccess     règles Apache : jolie adresse, refus de prives/
  index.php     la galerie, et la page de mot de passe
  fichier.php   aperçus, originaux, archive ZIP
  api.php       l'administration, fermée par la clé
  commun.php    le code partagé — jamais servi
  <identifiant>/prives/   manifeste, aperçus, originaux d'une livraison
```

L'administration n'envoie donc **jamais de code** au serveur : seulement des
images, vérifiées comme telles à l'arrivée (un fichier PHP renommé en `.jpg`
est refusé), et un manifeste écrit par PHP lui-même. Les photos ne sont jamais
servies par Apache : elles vivent sous `prives/`, refusé par deux règles
indépendantes, et seul `fichier.php` les lit, après avoir retrouvé le fichier
par son identifiant dans le manifeste — aucun chemin ne vient de l'adresse.

L'archive « toutes les photos » est assemblée à la volée, sans rien écrire sur
le disque de l'hébergeur, et sa taille est annoncée d'avance pour que le
navigateur affiche une vraie progression. Un téléchargement coupé se reprend au
lieu de tout recommencer.

La publication du site **n'efface rien** chez OVH : les livraisons déjà en
ligne survivent à chaque mise à jour du portfolio.

Tests : `python3 -m unittest discover -s admin -p 'test_*.py'` (Pillow requis ;
les tests des livraisons en ligne s'exécutent si `php` est disponible).

## Modèle de contenu du portfolio

```
Événement (TOP 12 — 9ᵉ journée · Badminton · 28 mars 2026)
 └── Photos (source, légende, dimensions)
```

Un seul niveau. Le site rangeait autrefois les photos en séries (Badminton,
Judo) découpées en journées : une série de plus n'apportait qu'un clic de plus,
puisque la journée était le vrai sujet. Le sport survit comme **étiquette** —
écrit sur la carte, et filtre au-dessus de la liste dès qu'il y a deux sports.

Un événement sans photo apparaît dans la liste, marqué « À venir ».
Un événement peut être **masqué** : accessible par son lien, absent de la liste
et du sitemap — pratique pour une galerie réservée à un club.

Un événement **à la une** s'affiche en grand à l'arrivée sur le site, avec sa
couverture, son titre et sa date. Si rien n'est coché, le site met en avant les
trois événements les plus récents plutôt qu'un accueil vide.

Les anciennes adresses `/serie/<sport>/<journée>/` sont redirigées vers
`/evenement/<journée>/` par une règle Apache : aucun lien déjà partagé ne casse.

## Publication

`Publier.command` produit un dossier complet contenant :

- une **vraie page par événement** (`/evenement/top-12-9e-journee/`),
  avec son titre, sa description et son aperçu de partage
- `sitemap.xml`, `robots.txt` et les données structurées pour les moteurs de recherche
- les redirections des anciennes adresses, pour ne casser aucun lien existant
- `.htaccess` : redirection vers l'adresse unique du site, compression, cache
- une **vignette de 800 px par photo**, servie dans les mosaïques et les cartes
  d'événement — la visionneuse ouvre toujours l'original. Une page galerie passe
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

Les secrets sont à créer dans **Settings → Secrets and variables → Actions**,
onglet *Secrets* :

| Secret | Où le trouver |
|---|---|
| `OVH_FTP_SERVER` | Espace client OVH → Hébergements → FTP-SSH (`ftp.clusterXXX.hosting.ovh.net`) |
| `OVH_FTP_USERNAME` | même page — l'identifiant du compte FTP |
| `OVH_FTP_PASSWORD` | défini à la création du compte FTP, réinitialisable depuis la même page |
| `OVH_CLE_LIVRAISONS` | choisi par vous : la clé qui ouvre les livraisons clients en ligne. Facultatif — sans lui, cette rubrique reste inactive. Seule son empreinte est déposée, hors de la racine web |

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
quel appareil : événements, photos, une, textes, réglages. C'est la même
interface que sur le Mac.

La page est **entièrement statique** : elle ne porte aucun secret et, sans clé,
ne sait rien faire. Elle parle directement à GitHub, qui régénère et déploie le
site comme d'habitude. Rien à protéger côté hébergeur pour le portfolio ; seules
les livraisons clients y ajoutent quelques fichiers PHP, décrits plus haut.

À la première visite sur un appareil, collez une clé GitHub *fine-grained*
limitée à ce dépôt, avec **Contents : Read and write**
(https://github.com/settings/personal-access-tokens). Elle reste dans ce
navigateur et n'est envoyée qu'à GitHub. Le bouton **Oublier la clé** l'efface
de l'appareil ; pour la désactiver partout — appareil perdu, par exemple —
révoquez-la sur GitHub, l'effacer localement ne suffit pas.

Les photos sont réduites **dans le navigateur** avant l'envoi : une photo de
8 Mo part en quelques centaines de kilooctets, ce qui rend l'envoi depuis un
téléphone en 4G supportable. Tant qu'elles ne sont pas publiées, elles vivent
dans le navigateur — l'administration les affiche depuis là, et un onglet
rechargé les retrouve intactes.

Les modifications s'accumulent et ne partent qu'au clic sur **Publier en ligne ↑**,
en une seule fois. Vingt photos font une publication, pas vingt. Tant que rien
n'est publié, quitter la page demande confirmation, et le texte en cours est
conservé pour la prochaine ouverture.

Les **livraisons clients** ont leur propre chemin : leurs photos sont trop
lourdes pour Git, elles montent donc directement chez OVH, avec leur propre clé
(voir plus haut). Là non plus, rien à installer ni à transférer à la main.

## Prérequis

L'administration **en ligne** ne demande rien : un navigateur suffit. Les
livraisons clients en ligne demandent **PHP chez l'hébergeur** — fourni par
OVH mutualisé.

Pour l'administration locale :

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
