<?php
/**
 * Points d'accès JSON de l'administration en ligne.
 *
 * Le contenu n'est pas écrit sur ce serveur : il est enregistré dans le
 * dépôt GitHub, qui régénère puis redéploie le site. C'est ce qui permet
 * de garder l'historique, les sauvegardes et les pages par série.
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

// Toute écriture doit porter le jeton de session : une autre page ouverte
// dans le même navigateur ne peut pas commander l'administration.
if ($post && !csrf_valide($_SERVER['HTTP_X_CSRF'] ?? ($_POST['csrf'] ?? null))) {
    repondre_json(['erreur' => 'Jeton de sécurité invalide. Rechargez la page.'], 403);
}

try {
    switch ($route) {

        case 'session':
            repondre_json(['ok' => true, 'csrf' => jeton_csrf(),
                           'depot' => reglage('depot'), 'branche' => branche()]);

        case 'data':
            if (!$post) {
                $f = lire_fichier_depot(DEPOT_FICHIER_DONNEES);
                if ($f['contenu'] === null) {
                    repondre_json(['erreur' => 'data.js est introuvable dans le dépôt.'], 404);
                }
                repondre_json(['donnees' => decoder_donnees($f['contenu']),
                               'sha' => $f['sha']]);
            }
            $envoi = json_decode((string) file_get_contents('php://input'), true);
            if (!is_array($envoi) || !isset($envoi['donnees']) || !is_array($envoi['donnees'])) {
                repondre_json(['erreur' => 'Contenu envoyé illisible.'], 400);
            }
            $d = $envoi['donnees'];
            if (!isset($d['series']) || !is_array($d['series'])) {
                repondre_json(['erreur' => 'Contenu incomplet : refus d’écraser le site.'], 400);
            }
            $sha = isset($envoi['sha']) && is_string($envoi['sha']) ? $envoi['sha'] : null;
            if ($sha === null) {
                // sans empreinte, on écraserait une modification faite ailleurs
                $sha = lire_fichier_depot(DEPOT_FICHIER_DONNEES)['sha'];
            }
            $rep = ecrire_fichier_depot(
                DEPOT_FICHIER_DONNEES, encoder_donnees($d), $sha,
                'Contenu du site — ' . date('d/m/Y à H:i') . ' (administration en ligne)'
            );
            repondre_json(['ok' => true,
                           'sha' => $rep['content']['sha'] ?? null,
                           'message' => 'Enregistré — le site sera à jour dans quelques minutes']);

        case 'etat':
            // dernier déploiement connu, pour dire où en est la mise en ligne
            [$code, $rep] = github('GET', '/repos/' . reglage('depot')
                . '/actions/runs?per_page=1&branch=' . rawurlencode(branche()));
            if ($code !== 200 || empty($rep['workflow_runs'][0])) {
                repondre_json(['connu' => false]);
            }
            $r = $rep['workflow_runs'][0];
            repondre_json(['connu' => true,
                           'statut' => $r['status'] ?? '',
                           'issue' => $r['conclusion'] ?? '',
                           'quand' => $r['created_at'] ?? '']);

        default:
            repondre_json(['erreur' => 'Requête inconnue.'], 404);
    }
} catch (Throwable $e) {
    repondre_json(['erreur' => $e->getMessage()], 500);
}
