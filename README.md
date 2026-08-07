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

Renseignez l'adresse du site dans **Administration → Réglages** avant la première
publication : sans elle, pas de sitemap ni d'aperçus de partage corrects.

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
