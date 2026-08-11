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
$installer = installation_possible();

// Premier lancement : le mot de passe se choisit ici, une seule fois.
if ($installer && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $a = (string) ($_POST['mdp'] ?? '');
    $b = (string) ($_POST['mdp2'] ?? '');
    if (!csrf_valide($_POST['csrf'] ?? null)) {
        $erreur = 'Formulaire expiré. Réessayez.';
    } elseif ($a !== $b) {
        $erreur = 'Les deux saisies sont différentes.';
    } elseif (mb_strlen($a) < 10) {
        $erreur = 'Trop court : 10 caractères au minimum. Cette page est '
                . 'accessible depuis Internet.';
    } else {
        $souci = enregistrer_mdp($a);
        if ($souci !== null) {
            $erreur = $souci;
        } else {
            oublier_echecs();
            connecter();
            header('Location: ./');
            exit;
        }
    }
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && !$installer && !connecte()) {
    $attente = attente_requise();
    if ($attente > 0) {
        $erreur = 'Trop de tentatives. Réessayez dans '
                . ($attente > 60 ? ceil($attente / 60) . ' minutes' : $attente . ' secondes') . '.';
    } elseif (!csrf_valide($_POST['csrf'] ?? null)) {
        $erreur = 'Formulaire expiré. Réessayez.';
    } elseif (!configuree()) {
        $erreur = "L'administration n'est pas configurée sur ce serveur.";
    } elseif (mdp_correct((string) ($_POST["mdp"] ?? ""), reglage("mdp_hash"))) {
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
    // L'interface est celle de l'administration locale, servie telle quelle.
    // Ces deux valeurs lui suffisent pour viser api.php au lieu de /api/.
    if (is_file(__DIR__ . '/interface.html')) {
        $tete = '<script>window.SBT_API=' . json_encode('api.php?r=')
              . ';window.SBT_CSRF=' . json_encode(jeton_csrf()) . ';</script>';
        $html = (string) file_get_contents(__DIR__ . '/interface.html');
        // avant le script de l'interface, qui lit ces valeurs au chargement
        $pos = strpos($html, '<script>');
        echo $pos === false ? $tete . $html
                            : substr($html, 0, $pos) . $tete . substr($html, $pos);
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
  <p class="sous"><?= $installer ? 'Premier lancement' : 'Réservé au photographe' ?></p>
<?php if ($erreur !== ''): ?>
  <div class="ko"><?= htmlspecialchars($erreur, ENT_QUOTES) ?></div>
<?php endif; ?>
<?php if ($installer): ?>
  <p class="sous" style="text-align:left">Choisissez le mot de passe qui protégera
    l'administration. C'est le seul à retenir : notez-le quelque part.</p>
  <form method="POST" autocomplete="off">
    <input type="hidden" name="csrf" value="<?= htmlspecialchars($jeton, ENT_QUOTES) ?>">
    <label for="mdp">Nouveau mot de passe</label>
    <input id="mdp" name="mdp" type="password" autocomplete="new-password"
           minlength="10" required autofocus>
    <label for="mdp2">Répétez-le</label>
    <input id="mdp2" name="mdp2" type="password" autocomplete="new-password"
           minlength="10" required>
    <button type="submit">Enregistrer et entrer</button>
  </form>
  <div class="pied">10 caractères au minimum. Cette page est accessible
    depuis Internet.</div>
<?php elseif (!configuree()): ?>
  <div class="ko">
<?php if (reglage('github_token') === ''): ?>
    L'administration n'est pas configurée sur ce serveur.
<?php else: ?>
    Le mot de passe n'a pas été choisi dans les 24 heures qui ont suivi
    l'installation. Relancez la publication depuis GitHub — onglet
    <em>Actions</em>, bouton <em>Run workflow</em> — puis revenez ici.
<?php endif; ?>
  </div>
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
