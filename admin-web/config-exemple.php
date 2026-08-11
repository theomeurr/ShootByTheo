<?php
/**
 * Modèle du fichier de configuration de l'administration en ligne.
 *
 * Le vrai fichier n'est PAS dans ce dépôt : il est écrit à la publication
 * à partir des secrets GitHub, et déposé à côté du dossier web pour ne
 * jamais être servi par Apache. Ce modèle sert de documentation.
 */
return [
    // Empreinte du mot de passe, produite par password_hash(..., PASSWORD_DEFAULT).
    // Jamais le mot de passe en clair.
    'mdp_hash'     => '$2y$12$exemple.exemple.exemple.exemple.exemple.exemple.ex',

    // Jeton GitHub à portée restreinte : ce dépôt seul, droit « Contents ».
    'github_token' => 'github_pat_xxx',

    'depot'        => 'theomeurr/ShootByTheo',
    'branche'      => 'main',

    // Durée d'une session ouverte, en secondes (12 h par défaut).
    'duree_session' => '43200',
];
