<?php
/**
 * Entrée de l'administration en ligne : connexion, puis l'interface.
 */
declare(strict_types=1);
require __DIR__ . '/commun.php';

$action = $_GET['a'] ?? '';

if ($action === 'sortie') {
    deconnecter();
    header('Location: ./');
    exit;
}

$erreur = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && !connecte()) {
    $attente = attente_requise();
    if ($attente > 0) {
        $erreur = 'Trop de tentatives. Réessayez dans '
                . ($attente > 60 ? ceil($attente / 60) . ' minutes' : $attente . ' secondes') . '.';
    } elseif (!csrf_valide($_POST['csrf'] ?? null)) {
        $erreur = 'Formulaire expiré. Réessayez.';
    } elseif (!configuree()) {
        $erreur = "L'administration n'est pas configurée sur ce serveur.";
    } elseif (password_verify((string) ($_POST['mdp'] ?? ''), reglage('mdp_hash'))) {
        oublier_echecs();
        connecter();
        header('Location: ./');
        exit;
    } else {
        noter_echec();
        $erreur = 'Mot de passe incorrect.';
    }
}

if (connecte()) {
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: same-origin');
    // L'interface adaptée à cette API n'est pas encore livrée : tant qu'elle
    // manque, on le dit plutôt que de servir une page dont rien ne marche.
    if (is_file(__DIR__ . '/interface.html')) {
        readfile(__DIR__ . '/interface.html');
    } else {
        echo '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
           , '<meta name="viewport" content="width=device-width,initial-scale=1">'
           , '<title>SBT — Administration</title></head>'
           , '<body style="background:#0c0b0a;color:#f2efe9;font-family:Helvetica,Arial,'
           , 'sans-serif;padding:32px;line-height:1.6"><p>Connexion réussie.</p>'
           , '<p style="color:#928c82">L\'interface d\'administration n\'est pas encore '
           , 'installée sur ce serveur.</p>'
           , '<p><a href="?a=sortie" style="color:#e2543a">Se déconnecter</a></p>'
           , '</body></html>';
    }
    exit;
}

header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
$jeton = jeton_csrf();
?>
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>SBT — Administration</title>
<style>
:root{--bg:#0c0b0a;--ink:#f2efe9;--accent:#e2543a;--line:rgba(242,239,233,.14);
      --panel:#141210;--muted:#928c82}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:var(--bg);color:var(--ink);padding:24px;
  font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.boite{width:100%;max-width:340px}
.marque{font-size:13px;font-weight:800;letter-spacing:.22em;text-transform:uppercase;
  text-align:center;margin-bottom:6px}
.marque span{color:var(--accent)}
.sous{text-align:center;color:var(--muted);font-size:12.5px;margin:0 0 28px}
form{display:flex;flex-direction:column;gap:12px}
label{font-size:12px;font-weight:600;letter-spacing:.04em;color:var(--muted)}
input{width:100%;background:var(--panel);border:1px solid var(--line);border-radius:8px;
  color:var(--ink);font-size:16px;padding:14px 15px;outline:none}
input:focus{border-color:var(--accent)}
button{border:none;border-radius:8px;background:var(--accent);color:var(--bg);
  font-size:14px;font-weight:700;padding:14px;cursor:pointer;margin-top:4px}
button:hover{filter:brightness(1.08)}
.ko{background:rgba(226,84,58,.12);border:1px solid rgba(226,84,58,.4);
  border-radius:8px;padding:11px 13px;font-size:13px;line-height:1.5;color:#f0b5a8}
.pied{margin-top:22px;text-align:center;font-size:11.5px;color:var(--muted);line-height:1.6}
.pied a{color:var(--muted)}
</style>
</head>
<body>
<div class="boite">
  <div class="marque">SBT <span>· Administration</span></div>
  <p class="sous">Réservé au photographe</p>
<?php if ($erreur !== ''): ?>
  <div class="ko"><?= htmlspecialchars($erreur, ENT_QUOTES) ?></div>
<?php endif; ?>
<?php if (!configuree()): ?>
  <div class="ko">Le fichier de configuration est absent sur ce serveur.
    L'administration en ligne ne peut pas fonctionner.</div>
<?php else: ?>
  <form method="POST" autocomplete="on">
    <input type="hidden" name="csrf" value="<?= htmlspecialchars($jeton, ENT_QUOTES) ?>">
    <label for="mdp">Mot de passe</label>
    <input id="mdp" name="mdp" type="password" autocomplete="current-password"
           required autofocus>
    <button type="submit">Entrer</button>
  </form>
<?php endif; ?>
<?php if (en_clair()): ?>
  <div class="pied" style="color:#e2a03a">Connexion non chiffrée — n'entrez pas
    votre mot de passe tant que l'adresse ne commence pas par « https ».</div>
<?php endif; ?>
  <div class="pied"><a href="/">← Retour au site</a></div>
</div>
</body>
</html>
