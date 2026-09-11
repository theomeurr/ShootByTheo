<?php
/**
 * Livraisons clients — code partagé.
 *
 * Un seul jeu de fichiers sert toutes les livraisons : chacune n'apporte que
 * ses données, sous prives/. L'administration ne dépose donc jamais de code
 * sur le serveur, seulement des photos et un manifeste.
 */
declare(strict_types=1);

const LIV_LARGEUR_APERCU = 1600;
const LIV_MAX_APERCU = 4 * 1024 * 1024;   // un aperçu de 1600 px n'atteint jamais cela

function liv_racine(): string { return __DIR__; }

/** Empreinte de la clé d'administration, déposée hors de la racine web. */
function liv_config(): array {
    static $c = null;
    if ($c !== null) { return $c; }
    $web = dirname(__DIR__);
    foreach ([dirname($web) . '/sbt-livraisons.php', $web . '/../sbt-livraisons.php'] as $p) {
        if (is_file($p)) {
            $v = require $p;
            if (is_array($v)) { return $c = $v; }
        }
    }
    return $c = [];
}

function liv_https(): bool {
    return !empty($_SERVER['HTTPS'])
        || ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https'
        || (string)($_SERVER['SERVER_PORT'] ?? '') === '443';
}

/* ------------------------------------------------------- identifiants */

function liv_id(string $id): string {
    if (!preg_match('/^[a-f0-9]{32}$/', $id)) {
        throw new RuntimeException('Identifiant de livraison invalide.');
    }
    return $id;
}

function liv_dossier(string $id): string { return liv_racine() . '/' . liv_id($id); }
function liv_prives(string $id): string { return liv_dossier($id) . '/prives'; }

function liv_manifeste(string $id): array {
    $p = liv_prives($id) . '/manifeste.json';
    if (!is_file($p)) { throw new RuntimeException('Livraison introuvable.'); }
    $d = json_decode((string)file_get_contents($p), true);
    if (!is_array($d)) { throw new RuntimeException('Manifeste illisible.'); }
    return $d;
}

function liv_ecrire_manifeste(string $id, array $d): void {
    $dir = liv_prives($id);
    if (!is_dir($dir)) { mkdir($dir, 0755, true); }
    $tmp = $dir . '/manifeste.tmp';
    file_put_contents($tmp, json_encode($d, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), LOCK_EX);
    rename($tmp, $dir . '/manifeste.json');
}

function liv_livraisons(): array {
    $out = [];
    foreach (glob(liv_racine() . '/*/prives/manifeste.json') ?: [] as $p) {
        $id = basename(dirname(dirname($p)));
        if (!preg_match('/^[a-f0-9]{32}$/', $id)) { continue; }
        $d = json_decode((string)file_get_contents($p), true);
        if (!is_array($d)) { continue; }
        $out[] = ['id' => $id, 'titre' => $d['titre'] ?? '', 'date' => $d['date'] ?? '',
                  'protege' => !empty($d['mdp']), 'photos' => count($d['photos'] ?? [])];
    }
    usort($out, function ($a, $b) { return strcmp($b['date'], $a['date']); });
    return $out;
}

/* --------------------------------------------------------- empreintes */

/** Vérifie un mot de passe ou une clé contre son empreinte PBKDF2. */
function liv_empreinte_ok(string $saisi, string $empreinte): bool {
    if ($empreinte === '') { return false; }
    if (strncmp($empreinte, 'pbkdf2$', 7) === 0) {
        $p = explode('$', $empreinte);
        if (count($p) !== 5) { return false; }
        [, $algo, $tours, $sel, $attendu] = $p;
        if (!in_array($algo, ['sha256', 'sha512'], true) || !ctype_xdigit($sel)
            || !ctype_xdigit($attendu) || (int)$tours < 1000) { return false; }
        return hash_equals($attendu,
            hash_pbkdf2($algo, $saisi, (string)hex2bin($sel), (int)$tours, 0, false));
    }
    return password_verify($saisi, $empreinte);
}

function liv_empreinte(string $clair): string {
    $sel = random_bytes(16);
    $tours = 210000;
    return 'pbkdf2$sha256$' . $tours . '$' . bin2hex($sel) . '$'
        . hash_pbkdf2('sha256', $clair, $sel, $tours, 0, false);
}

/* ------------------------------------------- limitation des tentatives */

function liv_essais(string $quoi): string {
    return sys_get_temp_dir() . '/sbt-liv-' . substr(sha1(__DIR__ . '|' . $quoi), 0, 16);
}

function liv_attente(string $quoi): int {
    $t = @json_decode((string)@file_get_contents(liv_essais($quoi)), true);
    if (!is_array($t)) { return 0; }
    $r = array_filter($t, function ($h) { return $h > time() - 1800; });
    $n = count($r);
    if ($n < 3) { return 0; }   // trois essais francs pour une faute de frappe
    return max(0, (min(300, 5 * (2 ** ($n - 3))) + max($r)) - time());
}

function liv_echec(string $quoi): void {
    $t = @json_decode((string)@file_get_contents(liv_essais($quoi)), true);
    $t = is_array($t) ? array_filter($t, function ($h) { return $h > time() - 1800; }) : [];
    $t[] = time();
    @file_put_contents(liv_essais($quoi), json_encode(array_values($t)), LOCK_EX);
}

function liv_oublier(string $quoi): void { @unlink(liv_essais($quoi)); }

/* ----------------------------------------------------------- diffusion */

/**
 * Diffuse un fichier privé. Une galerie entière peut peser plusieurs
 * gigaoctets : la lecture est découpée, et une reprise après coupure est
 * acceptée plutôt que de tout recommencer.
 */
function liv_envoyer(string $chemin, string $nom, string $type, bool $inline): void {
    if (!is_file($chemin)) { http_response_code(404); exit; }
    $taille = (int)filesize($chemin);
    $debut = 0; $fin = $taille - 1; $partiel = false;
    $plage = (string)($_SERVER['HTTP_RANGE'] ?? '');
    if ($plage !== '' && preg_match('/^bytes=(\d*)-(\d*)$/', $plage, $m)) {
        if ($m[1] === '' && $m[2] !== '') { $debut = max(0, $taille - (int)$m[2]); }
        else {
            $debut = (int)$m[1];
            if ($m[2] !== '') { $fin = min($fin, (int)$m[2]); }
        }
        if ($debut > $fin || $debut >= $taille) {
            http_response_code(416);
            header('Content-Range: bytes */' . $taille);
            exit;
        }
        $partiel = true;
    }
    while (ob_get_level() > 0) { ob_end_clean(); }
    http_response_code($partiel ? 206 : 200);
    header('Content-Type: ' . $type);
    header('Accept-Ranges: bytes');
    header('Content-Length: ' . (string)($fin - $debut + 1));
    header('Cache-Control: private, max-age=600');
    header('X-Robots-Tag: noindex, nofollow, noarchive');
    if ($partiel) { header(sprintf('Content-Range: bytes %d-%d/%d', $debut, $fin, $taille)); }
    header('Content-Disposition: ' . ($inline ? 'inline' : 'attachment')
        . '; filename*=UTF-8\'\'' . rawurlencode($nom));
    $f = fopen($chemin, 'rb');
    if ($f === false) { exit; }
    fseek($f, $debut);
    $reste = $fin - $debut + 1;
    while ($reste > 0 && !feof($f) && !connection_aborted()) {
        $bloc = fread($f, (int)min(262144, $reste));
        if ($bloc === false || $bloc === '') { break; }
        echo $bloc; flush();
        $reste -= strlen($bloc);
    }
    fclose($f);
    exit;
}

function liv_json($v, int $code = 200): void {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Robots-Tag: noindex, nofollow, noarchive');
    echo json_encode($v, JSON_UNESCAPED_UNICODE);
    exit;
}

/* ------------------------------------------------------------- sessions */

/** Chemin web du dossier « livraison », pour limiter le cookie à lui seul. */
function liv_base(): string {
    $s = str_replace('\\', '/', (string)($_SERVER['SCRIPT_NAME'] ?? '/livraison/index.php'));
    return rtrim(dirname($s), '/') . '/';
}

function liv_session(): void {
    if (session_status() === PHP_SESSION_ACTIVE) { return; }
    session_name('sbt_liv');
    session_set_cookie_params(['lifetime' => 0, 'path' => liv_base(),
        'secure' => liv_https(), 'httponly' => true, 'samesite' => 'Lax']);
    session_start();
}

function liv_ouverte(string $id): bool {
    liv_session();
    return !empty($_SESSION['ouvertes'][liv_id($id)]);
}

function liv_ouvrir(string $id): void {
    liv_session();
    $deja = $_SESSION['ouvertes'] ?? [];
    session_regenerate_id(true);
    $deja[liv_id($id)] = true;
    $_SESSION['ouvertes'] = $deja;
}

/** Une galerie sans mot de passe s'ouvre pour qui connaît son lien. */
function liv_acces(string $id, array $d): bool {
    return empty($d['mdp']) || liv_ouverte($id);
}

/* --------------------------------------------------------- galerie HTML */

function liv_h($v): string { return htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8'); }

function liv_galerie(string $id, array $d): string {
    $titre = liv_h($d['titre'] ?? 'Vos photos');
    $photos = array_values($d['photos'] ?? []);
    // La galerie répond à /livraison/<id>/ : une adresse relative y viserait
    // /livraison/<id>/fichier.php, qui n'existe pas.
    $lien = liv_h(liv_base()) . 'fichier.php?l=' . rawurlencode($id);
    $cartes = '';
    foreach ($photos as $i => $p) {
        $nom = liv_h($p['nom'] ?? '');
        $cartes .= '<article><button class="photo" data-index="' . $i . '" aria-label="Agrandir ' . $nom
            . '"><img src="' . $lien . '&amp;a=' . liv_h($p['id']) . '" alt="' . $nom
            . '" loading="lazy"></button><div class="caption"><span>' . $nom . '</span><a href="'
            . $lien . '&amp;o=' . liv_h($p['id']) . '" download="' . $nom . '">Télécharger ↓</a></div></article>';
    }
    return '<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive"><meta name="referrer" content="no-referrer">
<title>' . $titre . ' — SHOOTBYTHEO</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#111310;color:#eeeee7;font:16px/1.5 system-ui,sans-serif}header,main,footer{max-width:1440px;margin:auto;padding:32px 5vw}header{border-bottom:1px solid #34382e;display:flex;justify-content:space-between;gap:20px}.brand{font-weight:800;letter-spacing:.12em}.muted{color:#aaaF9f}.intro{padding:36px 0 45px;max-width:850px}h1{font-size:clamp(34px,6vw,72px);line-height:1.1;letter-spacing:-.045em;margin:16px 0 24px}a{color:inherit}button,a{touch-action:manipulation}button{font:inherit;cursor:pointer}.download{display:inline-block;padding:14px 22px;background:#d9edaf;color:#17200c;text-decoration:none;border-radius:6px;font-weight:650;margin-top:12px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px 20px}.photo{width:100%;padding:0;border:0;background:#20241c;border-radius:5px;overflow:hidden;display:block}.photo img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;transition:transform .25s}.photo:hover img{transform:scale(1.025)}.caption{display:flex;justify-content:space-between;gap:10px;font-size:12px;padding-top:10px}.caption span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#acb1a3}.caption a{flex-shrink:0}footer{color:#aaaF9f;font-size:13px;border-top:1px solid #34382e;margin-top:40px}dialog{width:96vw;max-width:1400px;max-height:96vh;border:1px solid #424936;padding:16px;background:#111310;color:#eeeee7}dialog::backdrop{background:#000d}.toolbar{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:10px}.toolbar button{border:1px solid #515946;border-radius:5px;background:#252c1e;color:inherit;padding:10px}#grand{display:block;width:100%;height:72vh;object-fit:contain}button:focus-visible,a:focus-visible{outline:3px solid #d9edaf;outline-offset:4px}@media(max-width:800px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.caption{flex-direction:column}header{font-size:12px}}@media(max-width:480px){.grid{grid-template-columns:1fr}.caption{flex-direction:row}#grand{height:62vh}.toolbar{flex-wrap:wrap}}@media(prefers-reduced-motion:reduce){.photo img{transition:none}}
</style></head><body><header><span class="brand">SHOOTBYTHEO</span><span class="muted">Votre galerie photo</span></header>
<main><section class="intro"><span class="muted">LIVRAISON · ' . count($photos) . ' PHOTOS</span><h1>' . $titre . '</h1><p>Vos images sont prêtes. Prenez le temps de les découvrir et téléchargez vos fichiers en qualité originale.</p><a class="download" href="' . $lien . '&amp;zip=1" download>Télécharger toutes les photos ↓</a></section>
<section class="grid" aria-label="Photos de la livraison">' . $cartes . '</section></main>
<footer>Galerie accessible aux personnes possédant ce lien. Conservez une copie de vos photos.</footer>
<dialog aria-label="Photo agrandie"><div class="toolbar"><button id="prev" aria-label="Photo précédente">←</button><span id="compteur"></span><a id="original" download>Télécharger l’original ↓</a><button id="next" aria-label="Photo suivante">→</button><button id="fermer">Fermer ×</button></div><img id="grand" alt=""></dialog>
<script>
const photos=Array.from(document.querySelectorAll("article")),dialog=document.querySelector("dialog");let index=0;
function afficher(n){index=(n+photos.length)%photos.length;const card=photos[index],img=card.querySelector("img"),link=card.querySelector("a");document.querySelector("#grand").src=img.src;document.querySelector("#grand").alt=img.alt;document.querySelector("#original").href=link.href;document.querySelector("#original").download=link.download;document.querySelector("#compteur").textContent=(index+1)+" / "+photos.length;}
document.querySelectorAll(".photo").forEach((b,i)=>b.addEventListener("click",()=>{afficher(i);dialog.showModal();}));
document.querySelector("#prev").onclick=()=>afficher(index-1);document.querySelector("#next").onclick=()=>afficher(index+1);document.querySelector("#fermer").onclick=()=>dialog.close();
dialog.addEventListener("keydown",e=>{if(e.key==="ArrowLeft"){e.preventDefault();afficher(index-1);}if(e.key==="ArrowRight"){e.preventDefault();afficher(index+1);}});
</script></body></html>';
}

/* ------------------------------------------------------------- archive */

function liv_nom_zip($titre): string {
    $b = preg_replace('/[^\p{L}\p{N} _-]+/u', ' ', (string)$titre);
    $b = trim((string)preg_replace('/\s+/u', ' ', (string)$b));
    if ($b === '') { $b = 'photos'; }
    return mb_substr($b, 0, 60) . '.zip';
}

/** Date et heure au format MS-DOS, seule horodatation que ZIP connaisse. */
function liv_zip_horodatage(int $t): array {
    $d = getdate($t);
    if ($d['year'] < 1980) { $d = getdate(315532800); }
    return [(($d['hours'] << 11) | ($d['minutes'] << 5) | ($d['seconds'] >> 1)),
            ((($d['year'] - 1980) << 9) | ($d['mon'] << 5) | $d['mday'])];
}

/** Deux photos peuvent porter le même nom : l'archive doit les distinguer. */
function liv_zip_noms(array $photos): array {
    $vus = []; $noms = [];
    foreach ($photos as $p) {
        $nom = (string)($p['nom'] ?? 'photo.jpg');
        $nom = str_replace(['\\', '/', "\0"], '-', $nom);
        if ($nom === '' || $nom === '.' || $nom === '..') { $nom = 'photo.jpg'; }
        $base = $nom; $n = 1;
        while (isset($vus[strtolower($nom)])) {
            $ext = strrchr($base, '.');
            $sans = ($ext === false) ? $base : substr($base, 0, -strlen($ext));
            $nom = $sans . ' (' . (++$n) . ')' . ($ext === false ? '' : $ext);
        }
        $vus[strtolower($nom)] = true;
        $noms[] = $nom;
    }
    return $noms;
}

const LIV_ZIP64 = 0xFFFFFFFF;        // valeur sentinelle du format
const LIV_ZIP64_SEUIL = 0xFFFFFFFF;  // au-delà, il faut les champs 64 bits

/**
 * Envoie toutes les photos en une archive construite à la volée : rien n'est
 * écrit sur le disque de l'hébergeur, et la taille annoncée d'avance donne au
 * navigateur une vraie barre de progression. Les JPEG sont déjà compressés :
 * les stocker tels quels évite de relire chaque fichier deux fois.
 */
function liv_zip_envoyer(array $fichiers, string $nom_archive): void {
    // --- premier passage : positions et taille totale, sans lire les données
    $e = [];
    $offset = 0;
    foreach ($fichiers as $f) {
        if (!is_file($f['chemin'])) { continue; }
        $taille = (int)filesize($f['chemin']);
        $nom = $f['nom'];
        $gros = $taille >= LIV_ZIP64_SEUIL;          // un seul fichier de plus de 4 Go
        $loin = $offset >= LIV_ZIP64_SEUIL;          // ou une archive qui dépasse 4 Go
        [$h, $j] = liv_zip_horodatage((int)(filemtime($f['chemin']) ?: time()));
        $e[] = ['chemin' => $f['chemin'], 'nom' => $nom, 'taille' => $taille,
                'gros' => $gros, 'loin' => $loin, 'offset' => $offset, 'h' => $h, 'j' => $j];
        $offset += 30 + strlen($nom) + ($gros ? 20 : 0) + $taille + ($gros ? 24 : 16);
    }
    if (!$e) { http_response_code(404); exit('Aucune photo à télécharger.'); }

    $cd_offset = $offset;
    $cd_taille = 0;
    foreach ($e as $x) {
        $n = ($x['gros'] ? 16 : 0) + ($x['loin'] ? 8 : 0);
        $cd_taille += 46 + strlen($x['nom']) + ($n ? $n + 4 : 0);
    }
    $queue = ($cd_offset + $cd_taille >= LIV_ZIP64_SEUIL || count($e) > 0xFFFF) ? 76 : 0;
    $total = $cd_offset + $cd_taille + $queue + 22;

    while (ob_get_level() > 0) { ob_end_clean(); }
    @set_time_limit(0);
    http_response_code(200);
    header('Content-Type: application/zip');
    header('Content-Length: ' . (string)$total);
    header('Accept-Ranges: none');
    header('Cache-Control: private, no-store');
    header('X-Robots-Tag: noindex, nofollow, noarchive');
    header('Content-Disposition: attachment; filename*=UTF-8\'\'' . rawurlencode($nom_archive));

    // --- second passage : en-tête, données et somme de contrôle, fichier par
    // fichier. La somme n'étant connue qu'après lecture, elle suit les données
    // (« data descriptor »), ce que tout décompresseur sait lire.
    $central = '';
    foreach ($e as &$x) {
        $z64 = $x['gros'];
        $extra = $z64 ? pack('vvPP', 0x0001, 16, 0, 0) : '';
        echo pack('VvvvvvVVVvv', 0x04034b50, $z64 ? 45 : 20, 0x0808, 0,
                  $x['h'], $x['j'], 0, 0, 0, strlen($x['nom']), strlen($extra));
        echo $x['nom'], $extra;
        $crc = hash_init('crc32b');
        $f = fopen($x['chemin'], 'rb');
        if ($f === false) { exit; }
        while (!feof($f) && !connection_aborted()) {
            $bloc = fread($f, 262144);
            if ($bloc === false || $bloc === '') { break; }
            hash_update($crc, $bloc);
            echo $bloc;
            flush();
        }
        fclose($f);
        $x['crc'] = (int)hexdec(hash_final($crc));
        echo pack('VV', 0x08074b50, $x['crc']);
        echo $z64 ? pack('PP', $x['taille'], $x['taille'])
                  : pack('VV', $x['taille'], $x['taille']);
        if (connection_aborted()) { exit; }
    }
    unset($x);

    foreach ($e as $x) {
        $extra = '';
        if ($x['gros']) { $extra .= pack('PP', $x['taille'], $x['taille']); }
        if ($x['loin']) { $extra .= pack('P', $x['offset']); }
        if ($extra !== '') { $extra = pack('vv', 0x0001, strlen($extra)) . $extra; }
        $central .= pack('VvvvvvvVVVvvvvvVV', 0x02014b50, 0x032D, $x['gros'] ? 45 : 20,
            0x0808, 0, $x['h'], $x['j'], $x['crc'],
            $x['gros'] ? LIV_ZIP64 : $x['taille'], $x['gros'] ? LIV_ZIP64 : $x['taille'],
            strlen($x['nom']), strlen($extra), 0, 0, 0, 0x81A40000,
            $x['loin'] ? LIV_ZIP64 : $x['offset']) . $x['nom'] . $extra;
    }
    echo $central;

    $n = count($e);
    if ($queue) {
        echo pack('VPvvVVPPPP', 0x06064b50, 44, 0x032D, 45, 0, 0, $n, $n, $cd_taille, $cd_offset);
        echo pack('VVPV', 0x07064b50, 0, $cd_offset + $cd_taille, 1);
    }
    echo pack('VvvvvVVv', 0x06054b50, 0, 0, min($n, 0xFFFF), min($n, 0xFFFF),
        $cd_taille >= LIV_ZIP64_SEUIL ? LIV_ZIP64 : $cd_taille,
        $cd_offset >= LIV_ZIP64_SEUIL ? LIV_ZIP64 : $cd_offset, 0);
    flush();
    exit;
}

/* -------------------------------------------------------------- images */

/** Extension réelle du fichier, déduite de son contenu et non de son nom. */
function liv_type_image(string $chemin): string {
    $info = @getimagesize($chemin);
    if (!is_array($info)) { return ''; }
    switch ($info[2]) {
        case IMAGETYPE_JPEG: return 'jpg';
        case IMAGETYPE_PNG:  return 'png';
        case IMAGETYPE_WEBP: return 'webp';
    }
    return '';
}

function liv_octets(string $reglage): int {
    $v = trim((string)ini_get($reglage));
    if ($v === '') { return 0; }
    $n = (int)$v;
    switch (strtolower(substr($v, -1))) {
        case 'g': $n *= 1024;
        // no break
        case 'm': $n *= 1024;
        // no break
        case 'k': $n *= 1024;
    }
    return $n;
}

/**
 * Plus gros original que l'hébergement accepte. L'aperçu voyage dans le même
 * envoi : la place qu'il occupe est retirée d'avance, sinon PHP jetterait
 * l'ensemble sans rien dire dès que le total dépasse post_max_size.
 */
function liv_max_envoi(): int {
    $max = liv_octets('upload_max_filesize');
    $poste = liv_octets('post_max_size');
    if ($poste > 0) {
        $place = max(65536, $poste - LIV_MAX_APERCU - 65536);
        $max = $max > 0 ? min($max, $place) : $place;
    }
    return (int)$max;
}

/** Une taille lisible : « 119 Mo », « 2,4 Mo », « 640 Ko ». */
function liv_taille(int $o): string {
    if ($o >= 10485760) { return (string)(int)round($o / 1048576) . ' Mo'; }
    if ($o >= 1048576) { return str_replace('.', ',', (string)round($o / 1048576, 1)) . ' Mo'; }
    return (string)max(1, (int)round($o / 1024)) . ' Ko';
}

function liv_raison_envoi(int $code): string {
    switch ($code) {
        case UPLOAD_ERR_INI_SIZE:
        case UPLOAD_ERR_FORM_SIZE:
            $m = liv_max_envoi();
            return 'Photo trop lourde pour l’hébergement'
                . ($m ? ' (limite : ' . liv_taille($m) . ').' : '.');
        case UPLOAD_ERR_PARTIAL:   return 'Envoi interrompu. Réessayez cette photo.';
        case UPLOAD_ERR_NO_FILE:   return 'Aucun fichier reçu.';
        case UPLOAD_ERR_NO_TMP_DIR:
        case UPLOAD_ERR_CANT_WRITE: return "L'hébergement n'a pas pu enregistrer le fichier.";
    }
    return "L'envoi a échoué.";
}

/**
 * Filet de secours quand le navigateur n'a pas fourni d'aperçu. GD peut
 * manquer, ou manquer de mémoire sur une très grande image : l'échec est
 * silencieux et rendu à l'appelant.
 */
function liv_apercu_gd(string $source, string $cible): bool {
    if (!function_exists('imagecreatetruecolor')) { return false; }
    $info = @getimagesize($source);
    if (!is_array($info)) { return false; }
    [$l, $h] = $info;
    if ($l < 1 || $h < 1) { return false; }
    $lire = [IMAGETYPE_JPEG => 'imagecreatefromjpeg', IMAGETYPE_PNG => 'imagecreatefrompng',
             IMAGETYPE_WEBP => 'imagecreatefromwebp'][$info[2]] ?? '';
    if ($lire === '' || !function_exists($lire)) { return false; }
    $src = @$lire($source);
    if (!$src) { return false; }
    $f = min(1.0, LIV_LARGEUR_APERCU / max($l, $h));
    $nl = max(1, (int)round($l * $f));
    $nh = max(1, (int)round($h * $f));
    $dst = @imagecreatetruecolor($nl, $nh);
    if (!$dst) { imagedestroy($src); return false; }
    imagefill($dst, 0, 0, imagecolorallocate($dst, 255, 255, 255));
    $ok = @imagecopyresampled($dst, $src, 0, 0, 0, 0, $nl, $nh, $l, $h)
        && @imagejpeg($dst, $cible, 85);
    imagedestroy($src);
    imagedestroy($dst);
    return (bool)$ok;
}
