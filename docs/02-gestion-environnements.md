# Document 02 - Gestion des Environnements

Ce document décrit le rôle des fichiers `.env` dans le Lot 1.

## Fichiers
- `.env.example` : Template neutre, à commiter dans le dépôt.
- `.env.dev` : Fichier de travail local, contient des clés de test (`devkey`, `devsecret`). Ignoré par git.
- `.env.prod` : Fichier sécurisé pour le serveur distant (à ne jamais commiter).

## Script de Validation
Avant tout démarrage (et avant de passer à l'étape suivante), le script `env/verify_env.ps1` est utilisé.
Il crée un conteneur temporaire Docker pour s'assurer que le fichier `.env.dev` est sain et ne fera pas crasher l'infrastructure LiveKit de manière silencieuse.
