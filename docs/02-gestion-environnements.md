# Document 02 - Gestion des Environnements

Ce document décrit le rôle des fichiers `.env` dans le Lot 1.

## Fichiers
- `.env.example` : Template neutre, à commiter dans le dépôt.
- `.env.dev.example` : modèle versionné de développement. Le copier vers `.env.dev`, ignoré par Git.
- `.env.prod.example` : modèle versionné de production. Le copier vers `.env.prod`, ignoré par Git.

## Script de Validation
Avant tout démarrage (et avant de passer à l'étape suivante), le script `env/verify_env.ps1` est utilisé.
Il crée un conteneur temporaire Docker pour s'assurer que le fichier `.env.dev` est sain et ne fera pas crasher l'infrastructure LiveKit de manière silencieuse.
