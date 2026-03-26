Write-Host "Démarrage du conteneur LiveKit..." -ForegroundColor Cyan
docker compose up -d

Write-Host "Attente de 5 secondes pour permettre au serveur RTC de s'initialiser..."
Start-Sleep -Seconds 5

Write-Host "Test de l'API locale (ping HTTP)..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:7880/" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ TEST REUSSI : Le serveur LiveKit répond correctement au ping réseau sur le port 7880." -ForegroundColor Green
        Write-Host "Toutes les étapes d'infrastructure sont validées."
        exit 0
    } else {
        Write-Host "❌ ERREUR : Le serveur a répondu avec le statut $($response.StatusCode)." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ ERREUR CRITIQUE : Impossible de joindre l'API LiveKit. Le conteneur a dû crasher au démarrage." -ForegroundColor Red
    Write-Host "Voici les logs du conteneur pour le débogage :" -ForegroundColor Yellow
    docker compose logs
    exit 1
}
