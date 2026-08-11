<?php
/**
 * Socle de l'administration en ligne de SBT.
 *
 * Configuration, session, authentification et accès à GitHub. Ce fichier
 * ne contient aucun secret : ils vivent dans un fichier déposé à côté du
 * dossier web (donc jamais servi par Apache), écrit à la publication.
 */
declare(strict_types=1);

const DEPOT_FICHIER_DONNEES = 'data.js';
const LARGEUR_MAX  = 2000;   // côté long des photos publiées, comme le serveur local
const QUALITE_JPEG = 80;

/** Emplacements possibles du fichier de secrets, du plus sûr au moins sûr. */
function chemins_config(): array
{
    $racine = dirname(__DIR__);          // .../www
    return [
        dirname($racine) . '/sbt-config.php',   // hors de la racine web
        $racine . '/../sbt-config.php',
        __DIR__ . '/config.php',                // repli, protégé par .htaccess
    ];
}

function config(): array
{
    static $c = null;
    if ($c !== null) {
        return $c;
    }
    foreach (chemins_config() as $p) {
        if (is_file($p)) {
            $c = require $p;
            if (is_array($c)) {
                return $c;
            }
        }
    }
    $c = [];
    return $c;
}

function reglage(string $cle, string $defaut = ''): string
{
    if ($cle === 'mdp_hash') {
        // le mot de passe choisi sur la page prime, et vit dans son propre
        // fichier : la publication réécrit la configuration, pas celui-ci
        $p = chemin_mdp();
        if ($p !== null) {
            $m = require $p;
            if (is_array($m) && !empty($m['mdp_hash']) && is_string($m['mdp_hash'])) {
                return $m['mdp_hash'];
            }
        }
    }
    $c = config();
    return isset($c[$cle]) && is_string($c[$cle]) ? $c[$cle] : $defaut;
}

/** Emplacement du mot de passe choisi depuis la page, s'il existe. */
function chemin_mdp(): ?string
{
    foreach (chemins_config() as $p) {
        $m = dirname($p) . '/sbt-mdp.php';
        if (is_file($m)) {
            return $m;
        }
    }
    return null;
}

/** Où l'écrire : à côté du fichier de configuration trouvé. */
function chemin_mdp_a_creer(): ?string
{
    foreach (chemins_config() as $p) {
        if (is_file($p)) {
            return dirname($p) . '/sbt-mdp.php';
        }
    }
    return null;
}

/** L'administration n'est utilisable que si elle a été configurée. */
function configuree(): bool
{
    return reglage('mdp_hash') !== '' && reglage('github_token') !== ''
        && reglage('depot') !== '';
}

/**
 * Le mot de passe peut-il encore être choisi depuis la page ?
 *
 * Seulement s'il n'en existe aucun, et dans les heures qui suivent une
 * publication : sans cette limite, une administration installée puis
 * oubliée resterait indéfiniment ouverte au premier venu.
 */
const DELAI_INSTALLATION = 86400;   // 24 heures

function installation_possible(): bool
{
    if (reglage('mdp_hash') !== '' || reglage('github_token') === '') {
        return false;
    }
    return temps_restant_installation() > 0;
}

function temps_restant_installation(): int
{
    foreach (chemins_config() as $p) {
        if (is_file($p)) {
            return max(0, DELAI_INSTALLATION - (time() - (int) filemtime($p)));
        }
    }
    return 0;
}

/** Enregistre le mot de passe choisi. Renvoie null si tout s'est bien passé. */
function enregistrer_mdp(string $clair): ?string
{
    $p = chemin_mdp_a_creer();
    if ($p === null) {
        return "Le fichier de configuration est introuvable sur ce serveur.";
    }
    $contenu = "<?php return ['mdp_hash' => "
             . var_export(password_hash($clair, PASSWORD_DEFAULT), true) . "];\n";
    if (@file_put_contents($p, $contenu, LOCK_EX) === false) {
        return "Le serveur n'autorise pas l'écriture du mot de passe.";
    }
    @chmod($p, 0600);
    return null;
}

/**
 * Vérifie le mot de passe contre son empreinte.
 *
 * Deux formes sont acceptées : celle produite par admin/motdepasse.py, qui
 * n'exige que Python — absent des Mac récents, PHP ne peut pas être supposé
 * présent — et celle de password_hash() pour qui l'a sous la main.
 */
function mdp_correct(string $saisi, string $empreinte): bool
{
    if (str_starts_with($empreinte, 'pbkdf2$')) {
        $p = explode('$', $empreinte);
        if (count($p) !== 5) {
            return false;
        }
        [, $algo, $tours, $sel, $attendu] = $p;
        if (!in_array($algo, ['sha256', 'sha512'], true)
            || !ctype_xdigit($sel) || !ctype_xdigit($attendu)
            || (int) $tours < 1000) {
            return false;
        }
        $calcule = hash_pbkdf2($algo, $saisi, (string) hex2bin($sel), (int) $tours, 0, false);
        return hash_equals($attendu, $calcule);
    }
    return password_verify($saisi, $empreinte);
}

/* ------------------------------------------------------------------ session */

function demarrer_session(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    session_set_cookie_params([
        'lifetime' => 0,
        'path'     => '/',
        // le site force déjà HTTPS ; le cookie ne doit jamais partir en clair
        'secure'   => !en_clair(),
        'httponly' => true,
        'samesite' => 'Strict',
    ]);
    session_name('sbt_admin');
    session_start();
}

function en_clair(): bool
{
    return empty($_SERVER['HTTPS'])
        && ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') !== 'https'
        && ($_SERVER['SERVER_PORT'] ?? '') !== '443';
}

function connecte(): bool
{
    demarrer_session();
    if (empty($_SESSION['ouvert'])) {
        return false;
    }
    // une session oubliée sur un téléphone ne doit pas rester ouverte
    $limite = (int) (reglage('duree_session', '') ?: 43200);
    if (time() - (int) ($_SESSION['depuis'] ?? 0) > $limite) {
        deconnecter();
        return false;
    }
    return true;
}

function connecter(): void
{
    demarrer_session();
    session_regenerate_id(true);          // contre la fixation de session
    $_SESSION['ouvert'] = true;
    $_SESSION['depuis'] = time();
    $_SESSION['csrf']   = bin2hex(random_bytes(32));
}

function deconnecter(): void
{
    demarrer_session();
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $p = session_get_cookie_params();
        setcookie(session_name(), '', time() - 42000, $p['path'], $p['domain'],
                  $p['secure'], $p['httponly']);
    }
    session_destroy();
}

function jeton_csrf(): string
{
    demarrer_session();
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function csrf_valide(?string $jeton): bool
{
    demarrer_session();
    return is_string($jeton) && !empty($_SESSION['csrf'])
        && hash_equals($_SESSION['csrf'], $jeton);
}

/* ------------------------------------------------ limitation des tentatives */

function fichier_tentatives(): string
{
    // le nom dépend du dossier : deux installations ne se gênent pas
    return sys_get_temp_dir() . '/sbt-tentatives-' . substr(sha1(__DIR__), 0, 12);
}

/** Nombre de secondes à patienter, 0 si l'essai est permis. */
function attente_requise(): int
{
    $t = @json_decode((string) @file_get_contents(fichier_tentatives()), true);
    if (!is_array($t)) {
        return 0;
    }
    $recentes = array_filter($t, fn($h) => $h > time() - 1800);
    $n = count($recentes);
    // trois essais francs pour une faute de frappe, puis l'attente double
    // à chaque échec : 5 s, 10 s, 20 s… jusqu'à 5 minutes. Une liste de
    // mots de passe courants n'a plus le temps d'aboutir.
    if ($n < 3) {
        return 0;
    }
    $delai = min(300, 5 * 2 ** ($n - 3));
    $reste = ($delai + max($recentes)) - time();
    return max(0, $reste);
}

function noter_echec(): void
{
    $t = @json_decode((string) @file_get_contents(fichier_tentatives()), true);
    $t = is_array($t) ? array_filter($t, fn($h) => $h > time() - 900) : [];
    $t[] = time();
    @file_put_contents(fichier_tentatives(), json_encode(array_values($t)), LOCK_EX);
}

function oublier_echecs(): void
{
    @unlink(fichier_tentatives());
}

/* ------------------------------------------------------------------- GitHub */

/**
 * Appelle l'API GitHub. Renvoie [code, corps décodé].
 */
function github(string $methode, string $chemin, ?array $corps = null): array
{
    // l'adresse est réglable pour pouvoir éprouver ces appels hors ligne
    $base = reglage('api_base', '') ?: 'https://api.github.com';
    $ch = curl_init($base . $chemin);
    $entetes = [
        'Accept: application/vnd.github+json',
        'Authorization: Bearer ' . reglage('github_token'),
        'X-GitHub-Api-Version: 2022-11-28',
        'User-Agent: SBT-Administration',
    ];
    if ($corps !== null) {
        $entetes[] = 'Content-Type: application/json';
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($corps));
    }
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST  => $methode,
        CURLOPT_HTTPHEADER     => $entetes,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 30,
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_SSL_VERIFYHOST => 2,
    ]);
    $rep  = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);
    if ($rep === false) {
        throw new RuntimeException('GitHub injoignable : ' . $err);
    }
    return [$code, json_decode((string) $rep, true)];
}

function branche(): string
{
    return reglage('branche', '') ?: 'main';
}

/** Contenu et empreinte d'un fichier du dépôt. */
function lire_fichier_depot(string $chemin): array
{
    [$code, $rep] = github('GET', '/repos/' . reglage('depot') . '/contents/'
        . rawurlencode_chemin($chemin) . '?ref=' . rawurlencode(branche()));
    if ($code === 404) {
        return ['contenu' => null, 'sha' => null];
    }
    if ($code !== 200 || !isset($rep['content'])) {
        throw new RuntimeException(erreur_github($code, $rep));
    }
    return [
        'contenu' => base64_decode(str_replace("\n", '', $rep['content'])),
        'sha'     => $rep['sha'] ?? null,
    ];
}

/** Écrit un fichier dans le dépôt. $sha est nul pour une création. */
function ecrire_fichier_depot(string $chemin, string $contenu, ?string $sha,
                              string $message): array
{
    $corps = [
        'message' => $message,
        'content' => base64_encode($contenu),
        'branch'  => branche(),
    ];
    if ($sha !== null) {
        $corps['sha'] = $sha;
    }
    [$code, $rep] = github('PUT', '/repos/' . reglage('depot') . '/contents/'
        . rawurlencode_chemin($chemin), $corps);
    if ($code !== 200 && $code !== 201) {
        throw new RuntimeException(erreur_github($code, $rep));
    }
    return $rep;
}

/** rawurlencode sans écraser les séparateurs de dossiers. */
function rawurlencode_chemin(string $chemin): string
{
    return implode('/', array_map('rawurlencode', explode('/', $chemin)));
}

function erreur_github(int $code, $rep): string
{
    $m = is_array($rep) && isset($rep['message']) ? (string) $rep['message'] : '';
    if ($code === 401) {
        return "GitHub a refusé le jeton d'accès. Il a peut-être expiré.";
    }
    if ($code === 403) {
        return "GitHub refuse l'opération : le jeton n'a pas le droit d'écrire "
             . 'sur ce dépôt.' . ($m ? ' (' . $m . ')' : '');
    }
    if ($code === 409 || str_contains(strtolower($m), 'does not match')) {
        return 'Le contenu a changé entre-temps. Rechargez la page avant '
             . 'de réenregistrer.';
    }
    return 'GitHub a répondu ' . $code . ($m ? ' : ' . $m : '');
}

/* ------------------------------------------------------------------ données */

/** Extrait l'objet JSON de data.js. */
function decoder_donnees(string $js): array
{
    if (!preg_match('/\{.*\}/s', $js, $m)) {
        throw new RuntimeException('data.js est illisible.');
    }
    $d = json_decode($m[0], true);
    if (!is_array($d)) {
        throw new RuntimeException('data.js contient du JSON invalide.');
    }
    return $d;
}

function encoder_donnees(array $d): string
{
    return 'window.SITE_DATA = '
        . json_encode($d, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
                        | JSON_PRETTY_PRINT) . ";\n";
}

function repondre_json($valeur, int $code = 200): void
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode($valeur, JSON_UNESCAPED_UNICODE);
    exit;
}
