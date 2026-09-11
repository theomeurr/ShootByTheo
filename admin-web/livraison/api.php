<?php
/**
 * Administration des livraisons, appelée depuis /admin/.
 *
 * La clé d'administration reste dans le navigateur du photographe ; le serveur
 * n'en garde que l'empreinte, hors de la racine web. Une fois la clé vérifiée,
 * une session porte le reste : le calcul PBKDF2 n'a lieu qu'une fois, et le
 * jeton attendu en en-tête ferme la porte aux requêtes venues d'ailleurs.
 */
declare(strict_types=1);
require __DIR__ . '/commun.php';

function liv_erreur(string $m, int $code = 400): void { liv_json(['erreur' => $m], $code); }

function liv_verrou(string $id) {
    $dir = liv_prives($id);
    if (!is_dir($dir)) { mkdir($dir, 0755, true); }
    $f = fopen($dir . '/.verrou', 'c');
    if ($f !== false) { flock($f, LOCK_EX); }
    return $f;
}

function liv_deverrou($f): void {
    if ($f !== false && $f !== null) { flock($f, LOCK_UN); fclose($f); }
}

function liv_supprimer_dossier(string $chemin): void {
    if (!is_dir($chemin) || is_link($chemin)) { @unlink($chemin); return; }
    foreach (scandir($chemin) ?: [] as $e) {
        if ($e === '.' || $e === '..') { continue; }
        $p = $chemin . '/' . $e;
        if (is_dir($p) && !is_link($p)) { liv_supprimer_dossier($p); } else { @unlink($p); }
    }
    @rmdir($chemin);
}

/* ------------------------------------------------------------ la porte */

liv_session();
$config = liv_config();
$empreinte = (string)($config['cle'] ?? '');
$action = (string)($_GET['a'] ?? '');
$poste = $_SERVER['REQUEST_METHOD'] === 'POST';

if ($action === 'etat') {
    liv_json(['configure' => $empreinte !== '', 'admin' => !empty($_SESSION['liv_admin']),
              'max_octets' => liv_max_envoi()]);
}

if ($action === 'ouvrir') {
    if (!$poste) { liv_erreur('Méthode non autorisée.', 405); }
    if ($empreinte === '') {
        liv_erreur("Les livraisons en ligne ne sont pas encore configurées sur l'hébergement.", 503);
    }
    $attente = liv_attente('cle');
    if ($attente > 0) { liv_erreur('Trop de tentatives. Réessayez dans ' . $attente . ' secondes.', 429); }
    $corps = json_decode((string)file_get_contents('php://input'), true);
    if (!liv_empreinte_ok((string)($corps['cle'] ?? ''), $empreinte)) {
        liv_echec('cle');
        liv_erreur("Clé d'administration incorrecte.", 401);
    }
    liv_oublier('cle');
    session_regenerate_id(true);
    $_SESSION['liv_admin'] = true;
    $_SESSION['liv_jeton'] = bin2hex(random_bytes(16));
    liv_json(['ok' => true, 'jeton' => $_SESSION['liv_jeton'], 'max_octets' => liv_max_envoi()]);
}

if (empty($_SESSION['liv_admin'])) { liv_erreur("Clé d'administration requise.", 401); }
// Un site tiers peut faire signer une requête par le cookie, jamais poser cet
// en-tête : c'est lui, et non le cookie, qui autorise les modifications.
if (!hash_equals((string)($_SESSION['liv_jeton'] ?? ''), (string)($_SERVER['HTTP_X_JETON'] ?? ''))) {
    liv_erreur('Session expirée. Rechargez la page.', 401);
}

if ($action === 'fermer') {
    $_SESSION = [];
    session_destroy();
    liv_json(['ok' => true]);
}

if ($action === 'liste') { liv_json(['livraisons' => liv_livraisons()]); }

/* --------------------------------------------------------- une galerie */

function liv_publique(string $id, array $d): array {
    return ['id' => $id, 'titre' => $d['titre'] ?? '', 'date' => $d['date'] ?? '',
            'protege' => !empty($d['mdp']),
            'photos' => array_map(function ($p) {
                return ['id' => $p['id'] ?? '', 'nom' => $p['nom'] ?? '',
                        'octets' => (int)($p['octets'] ?? 0)];
            }, array_values($d['photos'] ?? []))];
}

if ($action === 'creer') {
    if (!$poste) { liv_erreur('Méthode non autorisée.', 405); }
    $corps = json_decode((string)file_get_contents('php://input'), true);
    $titre = trim((string)($corps['titre'] ?? ''));
    if ($titre === '' || mb_strlen($titre) > 200) {
        liv_erreur('Indiquez un titre de 1 à 200 caractères.');
    }
    $id = bin2hex(random_bytes(16));
    $prives = liv_prives($id);
    if (!mkdir($prives . '/originaux', 0755, true) || !mkdir($prives . '/apercus', 0755, true)) {
        liv_erreur("Impossible de créer le dossier de la livraison sur l'hébergement.", 500);
    }
    // Ceinture en plus des bretelles : même si la règle du dossier parent
    // sautait, Apache refuserait encore de servir ces fichiers.
    file_put_contents($prives . '/.htaccess',
        "Options -Indexes\nRequire all denied\n<IfModule !mod_authz_core.c>\n  Order allow,deny\n  Deny from all\n</IfModule>\n");
    $d = ['id' => $id, 'titre' => $titre, 'date' => gmdate('c'), 'photos' => []];
    liv_ecrire_manifeste($id, $d);
    liv_json(['livraison' => liv_publique($id, $d)]);
}

$id = (string)($_GET['l'] ?? '');
try { liv_id($id); $d = liv_manifeste($id); }
catch (Throwable $e) { liv_erreur('Livraison introuvable.', 404); }

if ($action === 'galerie') { liv_json(['livraison' => liv_publique($id, $d)]); }

if (!$poste) { liv_erreur('Méthode non autorisée.', 405); }

if ($action === 'mdp') {
    $corps = json_decode((string)file_get_contents('php://input'), true);
    $mdp = (string)($corps['mdp'] ?? '');
    $v = liv_verrou($id);
    $d = liv_manifeste($id);
    if ($mdp === '') { unset($d['mdp']); }
    elseif (mb_strlen($mdp) < 6) { liv_deverrou($v); liv_erreur("Choisissez un mot de passe d'au moins 6 caractères."); }
    else { $d['mdp'] = liv_empreinte($mdp); }
    liv_ecrire_manifeste($id, $d);
    liv_deverrou($v);
    liv_json(['livraison' => liv_publique($id, $d)]);
}

if ($action === 'renommer') {
    $corps = json_decode((string)file_get_contents('php://input'), true);
    $titre = trim((string)($corps['titre'] ?? ''));
    if ($titre === '' || mb_strlen($titre) > 200) { liv_erreur('Indiquez un titre de 1 à 200 caractères.'); }
    $v = liv_verrou($id);
    $d = liv_manifeste($id);
    $d['titre'] = $titre;
    liv_ecrire_manifeste($id, $d);
    liv_deverrou($v);
    liv_json(['livraison' => liv_publique($id, $d)]);
}

if ($action === 'supprimer') {
    liv_supprimer_dossier(liv_dossier($id));
    liv_json(['ok' => true]);
}

if ($action === 'retirer') {
    $corps = json_decode((string)file_get_contents('php://input'), true);
    $pid = (string)($corps['photo'] ?? '');
    $v = liv_verrou($id);
    $d = liv_manifeste($id);
    $reste = [];
    $trouve = false;
    foreach ($d['photos'] ?? [] as $p) {
        if (!$trouve && (string)($p['id'] ?? '') === $pid && $pid !== '') {
            $trouve = true;
            @unlink(liv_prives($id) . '/originaux/' . basename((string)$p['fichier']));
            @unlink(liv_prives($id) . '/apercus/' . basename((string)$p['id']) . '.jpg');
            continue;
        }
        $reste[] = $p;
    }
    $d['photos'] = $reste;
    liv_ecrire_manifeste($id, $d);
    liv_deverrou($v);
    liv_json(['livraison' => liv_publique($id, $d)]);
}

/* ------------------------------------------------------------- photos */

if ($action === 'photo') {
    // Au-delà de post_max_size, PHP vide $_POST et $_FILES sans lever d'erreur :
    // sans ce test, la photo semblerait n'avoir jamais été choisie.
    if (!$_FILES && !$_POST && (int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 0) {
        $m = liv_max_envoi();
        liv_erreur('Photo trop lourde pour l’hébergement'
            . ($m ? ' (limite : ' . liv_taille($m) . ').' : '.'), 413);
    }
    if (empty($_FILES['original']['tmp_name']) || !is_uploaded_file($_FILES['original']['tmp_name'])) {
        liv_erreur(liv_raison_envoi($_FILES['original']['error'] ?? UPLOAD_ERR_NO_FILE), 413);
    }
    $tmp = (string)$_FILES['original']['tmp_name'];
    $ext = liv_type_image($tmp);
    if ($ext === '') {
        @unlink($tmp);
        liv_erreur('Utilisez des photos JPEG, PNG ou WebP.');
    }
    $pid = bin2hex(random_bytes(16));
    $prives = liv_prives($id);
    foreach ([$prives . '/originaux', $prives . '/apercus'] as $dir) {
        if (!is_dir($dir)) { mkdir($dir, 0755, true); }
    }
    $cible = $prives . '/originaux/' . $pid . '.' . $ext;
    if (!move_uploaded_file($tmp, $cible)) {
        liv_erreur("L'hébergement a refusé d'écrire le fichier.", 500);
    }
    // L'aperçu arrive tout fait du navigateur : l'hébergement mutualisé n'a ni
    // la mémoire ni le temps de réduire un RAW de 40 Mo. Sans lui, GD prend le
    // relais si l'hébergement l'a activé.
    $apercu = $prives . '/apercus/' . $pid . '.jpg';
    $ok = false;
    if (!empty($_FILES['apercu']['tmp_name']) && is_uploaded_file($_FILES['apercu']['tmp_name'])
        && (int)$_FILES['apercu']['size'] <= LIV_MAX_APERCU
        && liv_type_image((string)$_FILES['apercu']['tmp_name']) === 'jpg') {
        $ok = move_uploaded_file((string)$_FILES['apercu']['tmp_name'], $apercu);
    }
    if (!$ok) { $ok = liv_apercu_gd($cible, $apercu); }
    if (!$ok) {
        @unlink($cible);
        liv_erreur("L'aperçu n'a pas pu être créé. Réessayez depuis un navigateur récent.", 500);
    }
    $nom = (string)($_POST['nom'] ?? $_FILES['original']['name'] ?? 'photo');
    $nom = str_replace(['\\', '/', "\0"], '-', $nom);
    $nom = mb_substr(trim($nom), 0, 200);
    if ($nom === '') { $nom = 'photo.' . $ext; }
    $v = liv_verrou($id);
    $d = liv_manifeste($id);
    $d['photos'][] = ['id' => $pid, 'nom' => $nom, 'fichier' => $pid . '.' . $ext,
                      'octets' => (int)filesize($cible)];
    liv_ecrire_manifeste($id, $d);
    liv_deverrou($v);
    liv_json(['livraison' => liv_publique($id, $d)]);
}

liv_erreur('Action inconnue.', 404);
