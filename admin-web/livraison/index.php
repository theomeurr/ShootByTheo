<?php
/**
 * Porte d'entrée des galeries clients : https://…/livraison/<identifiant>/
 * Sans mot de passe, le lien suffit ; sinon, le mot de passe ouvre une session
 * valable pour cette galerie seule.
 */
declare(strict_types=1);
require __DIR__ . '/commun.php';

header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
header('X-Robots-Tag: noindex, nofollow, noarchive');
header('Referrer-Policy: no-referrer');

function liv_introuvable(): void {
    http_response_code(404);
    echo '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
       . '<meta name="viewport" content="width=device-width, initial-scale=1">'
       . '<meta name="robots" content="noindex, nofollow, noarchive">'
       . '<title>Galerie introuvable — SHOOTBYTHEO</title>'
       . '<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;'
       . 'background:#111310;color:#eeeee7;font:16px/1.6 system-ui,sans-serif;text-align:center;padding:24px}'
       . '</style></head><body><div><p style="font-weight:800;letter-spacing:.12em;font-size:13px">SHOOTBYTHEO</p>'
       . '<h1 style="font-size:22px">Cette galerie n’existe pas</h1>'
       . '<p style="color:#acb1a3;font-size:14px">Le lien est peut-être incomplet, ou la livraison a été retirée.</p>'
       . '</div></body></html>';
    exit;
}

$id = (string)($_GET['l'] ?? '');
try {
    liv_id($id);
    $d = liv_manifeste($id);
} catch (Throwable $e) {
    liv_introuvable();
}

$erreur = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && !empty($d['mdp']) && !liv_ouverte($id)) {
    $attente = liv_attente('g-' . $id);
    if ($attente > 0) {
        $erreur = 'Trop de tentatives. Réessayez dans '
            . ($attente > 60 ? (string)(int)ceil($attente / 60) . ' minutes'
                             : (string)$attente . ' secondes') . '.';
    } elseif (liv_empreinte_ok((string)($_POST['mdp'] ?? ''), (string)$d['mdp'])) {
        liv_oublier('g-' . $id);
        liv_ouvrir($id);
        // Rejouer l'adresse demandée évite de deviner si mod_rewrite est en
        // place ; filtrée, elle ne peut ni injecter d'en-tête ni mener ailleurs.
        $retour = (string)($_SERVER['REQUEST_URI'] ?? '');
        if ($retour === '' || $retour[0] !== '/' || strpbrk($retour, "\r\n") !== false) {
            $retour = './?l=' . rawurlencode($id);
        }
        header('Location: ' . $retour);
        exit;
    } else {
        liv_echec('g-' . $id);
        $erreur = 'Mot de passe incorrect.';
    }
}

if (liv_acces($id, $d)) {
    echo liv_galerie($id, $d);
    exit;
}
$titre = liv_h($d['titre'] ?? 'Vos photos');
?>
<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="referrer" content="no-referrer">
<title><?= $titre ?> — SHOOTBYTHEO</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
padding:24px;background:#111310;color:#eeeee7;font:16px/1.6 system-ui,sans-serif}
.boite{width:100%;max-width:360px}
.marque{font-weight:800;letter-spacing:.12em;font-size:13px;text-align:center}
h1{font-size:22px;line-height:1.25;margin:14px 0 6px;text-align:center}
p{color:#acb1a3;font-size:13.5px;margin:0 0 22px;text-align:center}
label{display:block;font-size:13px;font-weight:600;margin-bottom:6px}
input{width:100%;background:#20241c;border:1px solid #424936;border-radius:6px;
color:inherit;font-size:16px;padding:13px 14px;outline:none}
input:focus{border-color:#d9edaf}
button{width:100%;margin-top:14px;border:0;border-radius:6px;background:#d9edaf;
color:#17200c;font:inherit;font-weight:650;padding:14px;cursor:pointer}
button:hover{filter:brightness(1.05)}
.ko{background:#3a201c;border:1px solid #7c3b31;border-radius:6px;padding:11px 13px;
font-size:13.5px;margin-bottom:18px;color:#f3c3b8}
.pied{margin-top:20px;font-size:12px;color:#8d9285;text-align:center}
button:focus-visible,input:focus-visible{outline:3px solid #d9edaf;outline-offset:3px}
</style></head><body>
<div class="boite">
  <div class="marque">SHOOTBYTHEO</div>
  <h1><?= $titre ?></h1>
  <p>Cette galerie est protégée. Entrez le mot de passe qui vous a été communiqué.</p>
<?php if ($erreur !== ''): ?>
  <div class="ko"><?= liv_h($erreur) ?></div>
<?php endif; ?>
  <form method="POST" action="" autocomplete="on">
    <label for="mdp">Mot de passe</label>
    <input id="mdp" name="mdp" type="password" autocomplete="current-password" required autofocus>
    <button type="submit">Voir mes photos</button>
  </form>
  <div class="pied">SHOOTBYTHEO — photographie sportive</div>
</div></body></html>
