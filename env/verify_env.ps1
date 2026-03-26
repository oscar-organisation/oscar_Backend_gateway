Write-Host "Verification du fichier .env.dev avec Docker..." -ForegroundColor Cyan

# Test de parsing du fichier d'environnement avec Docker
# Si le fichier contient des erreurs de formatage (espaces invisibles, syntaxes illégales), Docker refusera de démarrer le conteneur.
docker run --rm --env-file .env.dev alpine sh -c "echo 'Succes : Fichier valide ! Variables chargees avec succes.'"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ TEST REUSSI : .env.dev est parfaitement formaté et prêt pour LiveKit." -ForegroundColor Green
    exit 0
} else {
    Write-Host "❌ ERREUR : Le format de .env.dev est invalide." -ForegroundColor Red
    exit 1
}
