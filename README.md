# SHOOTBYTHEO — site portfolio

Site vitrine de photographie sportive et documentaire : judo, badminton, aviation.
Page unique, entièrement statique (HTML, CSS, JavaScript), sans base de données
ni serveur applicatif. Il s'héberge n'importe où, y compris sur un hébergement mutualisé.

## Utilisation au quotidien

**Double-cliquez sur `Administration.command`.** Le navigateur s'ouvre sur une
interface locale (127.0.0.1) qui permet de tout modifier sans toucher au code :

- **Page d'accueil** — les photos à la une, leur titre, leur cadrage
- **Séries** — Badminton, Judo… chacune contenant des **journées** datées
- **Journées** — une compétition, un match : photos, légendes, ordre, couverture
- **À propos / Prestations / Réglages** — les textes et informations du site

Les photos envoyées sont automatiquement redimensionnées pour le web.
Une suppression déplace le fichier dans `image/corbeille/` : rien n'est effacé.

**Double-cliquez sur `Publier.command`** pour préparer le dossier à mettre en ligne.
Il apparaît sur le Bureau, prêt à être déposé chez l'hébergeur.

> L'administration est un outil **local**, sans mot de passe. Elle n'écoute que sur
> cette machine et ne doit jamais être mise en ligne : le dossier de publication
> l'exclut automatiquement.

## Organisation des fichiers

| Chemin | Rôle |
|---|---|
| `index.html` | Le site entier : structure, styles et moteur d'affichage |
| `data.js` | Tout le contenu (séries, journées, photos, textes) — écrit par l'administration |
| `admin/serveur.py` | Serveur local de l'administration |
| `admin/interface.html` | Interface de l'administration |
| `admin/publier.py` | Génère le dossier à mettre en ligne |
| `image/web/` | Images de couverture optimisées |
| `image/galerie/<série>/` | Photos des galeries |
| `*.html` (racine) | Anciennes pages, converties en redirections à la publication |

## Modèle de contenu

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

## Pourquoi l'administration n'est pas en ligne

Elle l'a été, sur `/admin/`, derrière un mot de passe. Elle ne l'est plus.

Une page d'administration publique doit être défendue, et elle portait un
jeton GitHub capable d'écrire dans ce dépôt : mot de passe à retenir, fenêtre
d'installation à surveiller, fichier de configuration à tenir hors de portée
d'Apache. Beaucoup de protections pour un usage qui, en pratique, se fait
depuis le Mac où sont déjà les photos.

`Administration.command` n'écoute que sur cette machine. Il n'y a plus de mot
de passe, plus de jeton sur le serveur, et plus de page à défendre.

Le bouton **Publier en ligne ↑** de l'administration locale fait le `git push`
lui-même : le confort est le même, sans surface exposée.

> Si l'administration en ligne a déjà été déployée, la publication suivante
> retire `/admin/` du serveur ainsi que ses fichiers de configuration.
> Pensez aussi à **révoquer le jeton GitHub** dans
> https://github.com/settings/personal-access-tokens : le supprimer des
> secrets ne le désactive pas.

Côté OVH, activez le **certificat SSL gratuit** (Hébergements → Multisite) :
le site force `https://` et l'adresse unique déclarée dans les réglages.

## Prérequis

- macOS avec Python 3 (fourni avec les outils de développement Apple)
- La bibliothèque Pillow pour le traitement des images :
  ```
  python3 -m pip install --user Pillow
  ```

## À noter

Les photos originales en pleine résolution ne sont pas versionnées ici
(voir `.gitignore`) : ce dépôt est public, et elles constituent la valeur
vendue par le lien de téléchargement HD. Pensez à les sauvegarder ailleurs.
