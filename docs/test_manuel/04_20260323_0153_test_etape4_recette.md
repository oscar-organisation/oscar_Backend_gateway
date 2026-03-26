# Test Manuel - Etape 4 : Recette Backend Finale (Interface de Test Web)

**Date de validation :** 23-03-2026 01:53
**Composant vise :** Backend Total (Validation du Lot 1 sans Front-End)

## Objectif du test
Ce test final demontre que la video de votre supermarche traverse effectivement toutes les cloisons (du robot en Python, jusqu'au serveur LiveKit en Golang) pour atterrir dans une interface web standard (simulant le futur casque Meta Quest du teleoperateur).

## Prerequis
L'infrastructure globale doit etre active.
```powershell
# S'assurer que le reseau tourne
cd c:\PROJET-HETIC\PROJET-fin-etude\OSCAR\Code\V1\backend\infrastructure\livekit
docker compose up -d
```

## Protocol d'Execution

### 1. Generation du passeport d'entree (Le JSON)
Depuis un terminal, demandez a votre service de vous forger une carte d'acces :
```powershell
cd c:\PROJET-HETIC\PROJET-fin-etude\OSCAR\Code\V1\backend\services\token-generator
docker run --rm --env-file ../../env/.env.dev oscar-token-generator
```
Identifiez et copiez la section `"token": "eyJhbGciOi..."` imprimee dans le texte JSON. (C'est ce mot de passe illisible que le futur Front-End manipulera dynamiquement).

### 2. Branchement de l'Outil de Diagnostic Neutre
Afin de ne pas biaiser le test, nous allons utiliser l'outil d'evaluation fourni publiquement par les createurs de LiveKit :
1. Lancez votre navigateur habituel (Chrome/Edge/Firefox).
2. Rendez-vous sur la mire : [https://livekit.io/connection-test](https://livekit.io/connection-test)
3. Renseignez la zone de connexion :
   - **LiveKit URL** : `ws://127.0.0.1:7880`
   - **Token** : *(Collez le fameux jeton copie l'etape precedente)*
4. Cliquez sur **Connect**.

### 3. Criteres de Validation Mets-Metiers
**Preuve Mathematique et Visuelle :**
- L'indicateur passe instantanement au statut "Connected".
- Dans le panneau `Tracks` ou `Video`, vous observez immediatement l'apparition d'un flux externe envoye par le "Simulateur Robot".
- La video VEO du supermarche que vous avez telechargee s'affiche sur votre navigateur avec une latence quasiment nulle.
- Lorsque la video touche a sa fin, vous constatez qu'elle recommence avec une fluidite parfaite, prouvant que le robot virtuel restera operationnel 24h/24 sans interruption de la ligne reseau WebRTC.

A l'issue positive de ce test, le chantier Architecture & Reseau du **Lot 1** peut etre officiellement audite, declare conforme, et delivre a l'equipe d'ingenierie Front-End.
