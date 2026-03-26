# Test Manuel - Étape 2 : Serveur de Streaming (LiveKit)

**Date de validation :** 22-03-2026 18:21
**Composant visé :** Backend / API LiveKit et réseau RTC

## 🎯 Objectif du test
S'assurer manuellement que le serveur relais RTC (LiveKit) ne boucle pas au démarrage (crashing loop), qu'il lit correctement son fichier `livekit.yaml` sans le rejeter, et qu'il répond aux requêtes HTTP locales.

## 📝 Prérequis
- Le test de l'Étape 1 doit avoir été passé sans erreur.
- La machine locale ne doit pas avoir d'autre service utilisant le port `7880`.

## 🛠️ Exécution pas-à-pas
1. Ouvrir un terminal (`PowerShell`).
2. Se placer dans le dossier de configuration LiveKit :
   ```powershell
   cd c:\PROJET-HETIC\PROJET-fin-etude\OSCAR\Code\V1\backend\infrastructure\livekit
   ```
3. Il y a 2 façons de vérifier que l'infrastructure est UP.

**Option A - Via le script semi-automatisé :**
Exécutez la commande suivante :
```powershell
.\test_livekit.ps1
```

**Option B - Mode 100% manuel et interactif :**
```powershell
# 1. Démarrer le conteneur en arrière-plan
docker compose up -d

# 2. Après quelques secondes d'attente, déclencher un test réseau avec cmd
curl http://localhost:7880/
```

## ✅ Comportement et Résultat Attendu
- Avec l'Option A (script) : le message final doit être "✅ TEST REUSSI : Le serveur LiveKit répond correctement au ping réseau..."
- Avec l'Option B (curl) : le terminal doit simplement vous répondre un mot en brut : `OK`. S'il répond `OK`, le réseau RTC peut démarrer et réceptionner les vidéos.

## ❌ Comment débugger en cas d'erreur
Si la requête bloque "Connection Refused" ou échoue :
1. Inspectez minutieusement les logs bruts du serveur LiveKit en chargeant le conteneur :
   ```powershell
   docker logs oscar-livekit-server
   ```
2. Vérifiez qu'une erreur de syntaxe (ex: retour à la ligne yaml mal formaté) n'a pas été glissée dans `livekit.yaml`.
