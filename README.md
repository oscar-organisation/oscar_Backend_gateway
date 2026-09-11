# OSCAR Realtime Gateway

Infrastructure temps réel commune aux robots OSCAR. Ce dépôt porte le serveur
LiveKit, les outils d'émission de jetons, le simulateur média de repli et le
runtime embarqué installable sur les robots physiques.

## Structure

- `infrastructure/livekit/` : configuration et orchestration LiveKit.
- `services/media-simulator/` : source vidéo de démonstration.
- `services/token-generator/` : génération de jetons de développement.
- `services/edge-agent/` : package embarqué canonique ROS 2 + LiveKit.
- `docs/architecture/processes/` : contrats des flux média, commande et télémétrie.
- `tools/` : diagnostic réseau et utilitaires opérateur.

## Sécurité

Les fichiers versionnés dans `env/` servent uniquement d'exemples. Les clés,
jetons et mots de passe réels doivent être injectés au déploiement et ne doivent
jamais être ajoutés au dépôt.

## Déploiement local

```bash
cp env/.env.dev.example env/.env.dev
docker compose --env-file env/.env.dev \
  -f infrastructure/livekit/docker-compose.yml up --build
```

Consulter `docs/05-deploiement-production.md` avant toute mise en production.
