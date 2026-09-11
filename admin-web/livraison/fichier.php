<?php
/**
 * Diffusion des fichiers d'une livraison. Rien n'est servi par Apache : les
 * photos vivent sous prives/, et PHP ne les envoie qu'après avoir vérifié
 * l'accès et retrouvé le fichier par son identifiant dans le manifeste.
 */
declare(strict_types=1);
require __DIR__ . '/commun.php';

function liv_refus(int $code, string $texte): void {
    http_response_code($code);
    header('Content-Type: text/plain; charset=utf-8');
    header('X-Robots-Tag: noindex, nofollow, noarchive');
    exit($texte);
}

$id = (string)($_GET['l'] ?? '');
try {
    liv_id($id);
    $d = liv_manifeste($id);
} catch (Throwable $e) {
    liv_refus(404, 'Livraison introuvable.');
}
if (!liv_acces($id, $d)) {
    liv_refus(403, "Accès refusé : ouvrez d'abord la galerie.");
}

$prives = liv_prives($id);
$types = ['jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg',
          'png' => 'image/png', 'webp' => 'image/webp'];

if (isset($_GET['zip'])) {
    $noms = liv_zip_noms($d['photos'] ?? []);
    $fichiers = [];
    foreach (array_values($d['photos'] ?? []) as $i => $p) {
        $fichiers[] = ['chemin' => $prives . '/originaux/' . basename((string)$p['fichier']),
                       'nom' => $noms[$i]];
    }
    liv_zip_envoyer($fichiers, liv_nom_zip($d['titre'] ?? 'photos'));
}

// L'identifiant demandé est comparé au manifeste : aucun chemin ne vient de
// l'adresse, donc aucune sortie possible du dossier.
$apercu = (string)($_GET['a'] ?? '');
$original = (string)($_GET['o'] ?? '');
foreach ($d['photos'] ?? [] as $p) {
    $pid = (string)($p['id'] ?? '');
    if ($pid === '') { continue; }
    if ($apercu !== '' && hash_equals($pid, $apercu)) {
        liv_envoyer($prives . '/apercus/' . $pid . '.jpg', (string)$p['nom'], 'image/jpeg', true);
    }
    if ($original !== '' && hash_equals($pid, $original)) {
        $ext = strtolower((string)pathinfo((string)$p['fichier'], PATHINFO_EXTENSION));
        liv_envoyer($prives . '/originaux/' . basename((string)$p['fichier']), (string)$p['nom'],
                    $types[$ext] ?? 'application/octet-stream', false);
    }
}
liv_refus(404, 'Photo introuvable.');
