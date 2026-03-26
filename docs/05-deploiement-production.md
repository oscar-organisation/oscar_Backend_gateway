# 05 - Manuel de Déploiement Serveur (Cloud OVH / AWS)

L'infrastructure Backend du projet OSCAR (Lot 1) a été rigoureusement conçue pour être **"Zero Friction"**.
Le déploiement sur un vrai serveur Cloud est entièrement automatisé pour ne subir aucun problème réseau ou dépendance manquante. Le problème d'IP réseau ("NAT Loopback") du développement local est automatiquement aboli par l'utilisation de `livekit.prod.yaml`.

## 🖥️ 1. Prérequis du Serveur Cloud
* Un serveur fraîchement loué sous **Ubuntu 20.04/22.04 LTS** (ou Debian).
* Autoriser les ports suivants dans le pare-feu de votre hébergeur (Security Group) :
  * **TCP :** `7880` (API & WebSockets)
  * **TCP :** `7881` (Fallback WebRTC ICE)
  * **UDP :** `7882` (WebRTC Vidéo Direct - *Crucial*)

---

## 🚀 2. Procédure d'installation

### A. Transférer l'application
Envoyez le dossier `backend/` de notre code source vers votre nouveau serveur, soit par Github, soit par copie directe (SFTP/FileZilla).

### B. Mettre les vraies clés de sécurité
Sur le serveur physique, modifiez les clés factices par des vraies clés de sécurité inviolables (en évitant les espaces ou caractères très spéciaux) dans le fichier de production :
*(Fichier : `backend/env/.env.prod`)*
```bash
LIVEKIT_KEYS=oscar_prod_key:VOTRE_GRAND_SECRET_TRES_LONG_ALPHANUMERIQUE
```

### C. Lancer le Script Magique "One-Click"
C'est la seule commande technique que vous avez besoin de taper. 
Le script bash de déploiement va automatiquement : Installer un moteur Docker tout neuf s'il n'y en a pas, préparer les réseaux de votre serveur, assembler l'architecture LiveKit et démarrer la simulation robot.

Placez-vous dans le dossier, donnez les droits d'exécution, et frappez :
```bash
cd backend
chmod +x setup_server.sh
./setup_server.sh
```

---

## ✅ 3. Vérification du Succès (Recette de Production)

Si le script se termine par le grand message vert de succès, votre serveur est sur orbite.
Vérifiez que le robot Pousse bien la vidéo sur LiveKit :
```bash
docker logs oscar-media-simulator
```
S'il affiche `Canal vidéo ouvert et réservé dans la Room virtuelle`, le job est accompli.

**Côté Client (Meta Quest / Frontend) :**
Ils pourront désormais se connecter en entrant simplement l'Adresse IP de votre Serveur Cloud :
* URL : `ws://ADRESSE_IP_DU_SERVEUR:7880`
* Token : *(Généré par vous aves les vraies clés prod)*
