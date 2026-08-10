<?php
/**
 * Points d'accès de l'administration en ligne.
 *
 * Ils répondent comme ceux du serveur local (admin/serveur.py) : la même
 * interface sert les deux administrations, seule l'adresse de base change.
 *
 * Le contenu n'est pas écrit sur ce serveur mais dans le dépôt GitHub, qui
 * régénère puis redéploie le site. C'est ce qui préserve l'historique et
 * les pages par série, produites à partir de data.js.
 */
declare(strict_types=1);
require __DIR__ . '/commun.php';

header('X-Content-Type-Options: nosniff');

if (!connecte()) {
    repondre_json(['erreur' => 'Session expirée. Reconnectez-vous.',
                   'reconnexion' => true], 401);
}
if (!configuree()) {
    repondre_json(['erreur' => "L'administration n'est pas configurée."], 500);
}

$route = $_GET['r'] ?? '';
$post  = $_SERVER['REQUEST_METHOD'] === 'POST';

// Toute écriture porte le jeton de session : une autre page ouverte dans le
// même navigateur ne peut pas commander l'administration.
if ($post && !csrf_valide($_SERVER['HTTP_X_CSRF'] ?? ($_POST['csrf'] ?? null))) {
    repondre_json(['erreur' => 'Jeton de sécurité invalide. Rechargez la page.'], 403);
}

try {
    switch ($route) {

        /* ---------------------------------------------------------- contenu */
        case 'data':
            if (!$post) {
                $f = lire_fichier_depot(DEPOT_FICHIER_DONNEES);
                if ($f['contenu'] === null) {
                    repondre_json(['erreur' => 'data.js est introuvable dans le dépôt.'], 404);
                }
                // l'empreinte reste côté serveur : elle sert à détecter qu'une
                // modification a eu lieu ailleurs depuis le chargement
                $_SESSION['sha_data'] = $f['sha'];
                repondre_json(decoder_donnees($f['contenu']));
            }
            $d = json_decode((string) file_get_contents('php://input'), true);
            if (!is_array($d) || !isset($d['series']) || !is_array($d['series'])) {
                repondre_json(['erreur' => 'Contenu incomplet : refus d’écraser le site.'], 400);
            }
            $sha = $_SESSION['sha_data'] ?? lire_fichier_depot(DEPOT_FICHIER_DONNEES)['sha'];
            $rep = ecrire_fichier_depot(DEPOT_FICHIER_DONNEES, encoder_donnees($d), $sha,
                                        'Contenu du site — ' . horodatage());
            $_SESSION['sha_data'] = $rep['content']['sha'] ?? null;
            repondre_json(['ok' => true]);

        /* ------------------------------------------------ photos réutilisables */
        case 'images':
            repondre_json([
                'accueil' => lister_images('image/accueil'),
                'web'     => lister_images('image/web'),
            ]);

        /* --------------------------------------------------------- envoi photo */
        case 'upload':
            if (!$post) {
                repondre_json(['erreur' => 'Méthode invalide.'], 405);
            }
            repondre_json(envoyer_photo());

        /* ------------------------------------------------------- mise au rebut */
        case 'trash':
            if (!$post) {
                repondre_json(['erreur' => 'Méthode invalide.'], 405);
            }
            $p = json_decode((string) file_get_contents('php://input'), true);
            $srcs = $p['srcs'] ?? (isset($p['src']) ? [$p['src']] : []);
            repondre_json(['ok' => true, 'deplacees' => retirer_photos($srcs)]);

        /* ------------------------------------------------------- état, publier */
        case 'git':
            // en ligne, enregistrer publie déjà : pas de bouton séparé
            repondre_json(['actif' => false, 'enLigne' => true]);

        case 'session':
            repondre_json(['ok' => true, 'csrf' => jeton_csrf(),
                           'depot' => reglage('depot'), 'branche' => branche()]);

        default:
            repondre_json(['erreur' => 'Requête inconnue.'], 404);
    }
} catch (Throwable $e) {
    repondre_json(['erreur' => $e->getMessage()], 500);
}

/* ------------------------------------------------------------------ outils */

function horodatage(): string
{
    return date('d/m/Y à H:i') . ' (en ligne)';
}

/** Photos déjà présentes dans un dossier du dépôt. */
function lister_images(string $dossier): array
{
    [$code, $rep] = github('GET', '/repos/' . reglage('depot') . '/contents/'
        . rawurlencode_chemin($dossier) . '?ref=' . rawurlencode(branche()));
    if ($code !== 200 || !is_array($rep)) {
        return [];   // dossier absent : rien à proposer, ce n'est pas une erreur
    }
    $out = [];
    foreach ($rep as $e) {
        if (($e['type'] ?? '') === 'file'
            && preg_match('/\.(jpe?g|png|webp)$/i', (string) ($e['name'] ?? ''))) {
            $out[] = $dossier . '/' . $e['name'];
        }
    }
    sort($out);
    return $out;
}

/** Version PHP du slug de admin/serveur.py : mêmes noms de fichiers. */
function slug(string $texte): string
{
    $t = @iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $texte);
    if ($t === false) {
        $t = $texte;
    }
    $t = preg_replace('/[^a-zA-Z0-9]+/', '-', $t) ?? '';
    return strtolower(trim($t, '-'));
}

/**
 * Redimensionne la photo reçue et la dépose dans le dépôt.
 * Renvoie le chemin et les dimensions, comme le serveur local.
 */
function envoyer_photo(): array
{
    $brut = file_get_contents('php://input');
    if ($brut === false || strlen($brut) === 0) {
        throw new RuntimeException('Photo vide.');
    }
    if (strlen($brut) > 40 * 1024 * 1024) {
        throw new RuntimeException('Photo trop lourde (40 Mo maximum).');
    }
    $im = @imagecreatefromstring($brut);
    if ($im === false) {
        throw new RuntimeException("Ce fichier n'est pas une image lisible.");
    }
    $im = redresser($im, $brut);
    $l = imagesx($im);
    $h = imagesy($im);
    if ($l > LARGEUR_MAX) {
        $nh = (int) round($h * LARGEUR_MAX / $l);
        $petite = imagescale($im, LARGEUR_MAX, $nh, IMG_BICUBIC);
        if ($petite !== false) {
            imagedestroy($im);
            $im = $petite;
            $l = LARGEUR_MAX;
            $h = $nh;
        }
    }
    // aplatir sur blanc : un PNG transparent virerait au noir en JPEG
    $fond = imagecreatetruecolor($l, $h);
    imagefill($fond, 0, 0, imagecolorallocate($fond, 255, 255, 255));
    imagecopy($fond, $im, 0, 0, 0, 0, $l, $h);
    imagedestroy($im);

    ob_start();
    imagejpeg($fond, null, QUALITE_JPEG);
    $jpeg = (string) ob_get_clean();
    imagedestroy($fond);

    $dossier = $_GET['dossier'] ?? '';
    if ($dossier === 'accueil' || $dossier === 'apropos') {
        $dest = 'image/' . $dossier;
    } else {
        $dest = 'image/galerie/' . (slug($_GET['serie'] ?? 'galerie') ?: 'galerie');
    }
    $base = slug(pathinfo((string) ($_GET['name'] ?? 'photo'), PATHINFO_FILENAME)) ?: 'photo';
    $chemin = chemin_libre($dest, $base);

    ecrire_fichier_depot($chemin, $jpeg, null, 'Photo ' . basename($chemin) . ' — ' . horodatage());
    return ['src' => $chemin, 'largeur' => $l, 'hauteur' => $h];
}

/** Corrige l'orientation d'après les données EXIF de l'original. */
function redresser($im, string $brut)
{
    if (!function_exists('exif_read_data')) {
        return $im;
    }
    $exif = @exif_read_data('data://image/jpeg;base64,' . base64_encode($brut));
    $o = is_array($exif) ? (int) ($exif['Orientation'] ?? 0) : 0;
    if ($o === 3) {
        return imagerotate($im, 180, 0) ?: $im;
    }
    if ($o === 6) {
        return imagerotate($im, -90, 0) ?: $im;
    }
    if ($o === 8) {
        return imagerotate($im, 90, 0) ?: $im;
    }
    return $im;
}

/** Premier nom disponible : photo.jpg, photo-2.jpg, photo-3.jpg… */
function chemin_libre(string $dossier, string $base): string
{
    $existants = lister_images($dossier);
    $pris = array_flip($existants);
    $c = $dossier . '/' . $base . '.jpg';
    $n = 2;
    while (isset($pris[$c])) {
        $c = $dossier . '/' . $base . '-' . $n . '.jpg';
        $n++;
    }
    return $c;
}

/**
 * Retire des photos du dépôt. Rien n'est perdu : l'historique Git conserve
 * chaque version, c'est la corbeille du serveur local.
 */
function retirer_photos(array $srcs): array
{
    $faites = [];
    foreach ($srcs as $src) {
        if (!is_string($src) || !str_starts_with($src, 'image/') || str_contains($src, '..')) {
            continue;
        }
        $f = lire_fichier_depot($src);
        if ($f['sha'] === null) {
            continue;
        }
        [$code] = github('DELETE', '/repos/' . reglage('depot') . '/contents/'
            . rawurlencode_chemin($src), [
                'message' => 'Retire ' . basename($src) . ' — ' . horodatage(),
                'sha'     => $f['sha'],
                'branch'  => branche(),
            ]);
        if ($code === 200) {
            $faites[] = $src;
        }
    }
    return $faites;
}
