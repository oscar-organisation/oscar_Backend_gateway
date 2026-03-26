#!/bin/bash
set -e

echo "=========================================================="
echo "🚀 OSCAR - Installation Automatisée du Serveur Production"
echo "=========================================================="

# 1. Vérification de Docker
if ! command -v docker &> /dev/null
then
    echo "🐳 Docker est introuvable. Installation de Docker CE..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker installé."
else
    echo "✅ Docker est déjà installé."
fi

# 2. Vérification de Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null
then
    echo "🐳 Docker Compose introuvable. Installation du plugin..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

echo "🔧 Configuration de l'environnement de production..."
# S'assure que le script bash est exécuté depuis la racine backend
cd "$(dirname "$0")"

echo "✅ Environnement prêt. Démarrage de l'infrastructure..."
cd infrastructure/livekit

# Lancement sécurisé en forçant la lecture du fichier de variables de production
sudo docker compose --env-file ../../env/.env.prod up -d --build

echo "=========================================================="
echo "🎯 Déploiement terminé avec succès !"
echo "Le serveur LiveKit et le simulateur vidéo sont en ligne."
echo "Consultez les logs avec : docker logs oscar-livekit-server"
echo "=========================================================="
