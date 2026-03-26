echo "=========================================================="
echo "🚀 OSCAR - Lancement Automatisé (Local Dev) Zero Friction"
echo "=========================================================="

echo "🔍 Recherche de votre adresse IP locale..."

# 1. Détection intelligente de l'IP du développeur en ignorant les cartes virtuelles
$ipObj = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|vEthernet|WSL|Tailscale|Npcap' } | Select-Object -First 1

if ($ipObj) {
    $ip = $ipObj.IPAddress
    echo "✅ IP Développeur détectée : $ip"
} else {
    echo "⚠️ Impossible de détecter l'IP Wi-Fi/Ethernet automatiquement."
    $ip = "127.0.0.1"
}

# 2. Remplacement dynamique de l'IP dans le fichier yaml de configuration
# Cela assure que le serveur fonctionnera pour n'importe quel membre de l'équipe
$yamlPath = ".\infrastructure\livekit\livekit.yaml"
if (Test-Path $yamlPath) {
    $content = Get-Content $yamlPath
    # Remplace l'ancienne IP par la nouvelle IP, peu importe ce qu'elle était
    $content = $content -replace "node_ip:\s*.*", "node_ip: $ip"
    Set-Content -Path $yamlPath -Value $content
    echo "✅ Configuration LiveKit mise à jour automatiquement."
} else {
    echo "❌ Erreur: Impossible de trouver $yamlPath depuis ce dossier."
    exit 1
}

# 3. Démarrage de l'infrastructure
echo "⏳ Lancement de l'infrastructure Docker..."
cd infrastructure\livekit
docker compose --env-file ..\..\env\.env.dev up -d --build

echo "=========================================================="
echo "🎯 Système Prêt pour tester au sein de votre équipe !"
echo "=========================================================="
