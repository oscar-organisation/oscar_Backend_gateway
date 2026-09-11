
---

# P1 — Média immersif (vidéo et audio robot → opérateur)

## Ce que ce pipeline fait

Le P1 est le pipeline de **téléprésence** : il permet à l'opérateur, à distance dans son casque VR, de **voir** et d'**entendre** ce qui se passe autour du robot dans le supermarché. C'est l'équivalent de "regarder par les yeux du robot et écouter avec ses oreilles".

## Concrètement, qu'est-ce qui se passe ?

Le robot est équipé de capteurs média (caméras stéréo, micros, éventuellement lidar pour la profondeur). Ces capteurs produisent en continu :
- Un **flux vidéo** (typiquement 30 à 60 images par seconde, en résolution 1080p ou plus)
- Un **flux audio** (échantillonné à 48 kHz, mono ou stéréo)

Ces flux bruts sont récupérés par le **Media Agent** (Module Caméra & Micro), qui tourne dans le Cerveau du robot. Ce module fait trois choses :

1. **Encodage** : il compresse la vidéo (H.264 ou VP8) et l'audio (Opus) pour réduire la bande passante. La vidéo brute fait 1.5 Gbit/s, après encodage elle ne fait plus que 5-10 Mbit/s.
2. **Publication** : il pousse ces flux compressés dans LiveKit comme des "tracks" (pistes média).
3. **Adaptation** : selon la qualité du réseau, il ajuste automatiquement le bitrate (LiveKit gère ça nativement avec son Simulcast).

Côté pilote, le casque Quest s'abonne à ces tracks via l'application WebXR. LiveKit lui transmet les flux. L'application :

1. **Décode** la vidéo et l'audio
2. **Affiche** la vidéo dans le casque (en stéréo si caméras stéréo, sinon en mono)
3. **Diffuse** l'audio dans les écouteurs du casque

## Ce qu'il faut savoir techniquement

- **Latence cible** : sous 150 ms entre la capture par le capteur et l'affichage dans le casque. Au-delà, l'opérateur ressent un décalage gênant.
- **Encodage matériel** : si possible, utiliser un encodeur GPU (NVENC sur NVIDIA Jetson) pour ne pas saturer le CPU.
- **Audio bidirectionnel** : ce pipeline ne couvre que **robot → opérateur**. La voix de l'opérateur vers le robot est un autre cas (qui passe aussi par LiveKit mais avec d'autres acteurs).
- **Échec gracieux** : si LiveKit ralentit, la vidéo se dégrade (résolution baisse) avant de se couper. C'est le comportement standard WebRTC.

## Ce qui est volontairement absent de ce pipeline

- Pas de traitement IA (c'est P4)
- Pas de télémétrie (c'est P3)
- Pas de retour de commande (c'est P2)
- Pas de dialogue client (c'est P7)

Ce pipeline est volontairement **simple et performant** : son seul objectif c'est de transmettre le flux média en temps réel, sans logique métier ajoutée.

---

## Diagramme de séquence P1

````
```mermaid
sequenceDiagram
    autonumber

    box rgb(225,245,238) Robot - Capteurs physiques ou virtuels Isaac
        participant CAPTEURS as Capteurs Media<br/>(Caméras · micros · IMU · Haut-parleur)<br/>[HARDWARE] ou [HARDWARE VIRTUEL Isaac]
    end

    box rgb(238,237,254) Cerveau du robot - Ordinateur embarqué
        participant MEDIA as Media Agent<br/>(Module Caméra & Micro)<br/>[SOFTWARE]
    end

    box rgb(225,245,238) LiveKit - Pivot temps réel
        participant LK as LiveKit Room<br/>(Salle virtuelle temps réel)<br/>[SOFTWARE]
    end

    box rgb(230,241,251) Poste du pilote à distance
        participant WEBXR as WebXR / Three.js<br/>(Application VR du pilote)<br/>[SOFTWARE]
        participant QUEST as Casque Meta Quest<br/>(Casque de réalité virtuelle)<br/>[HARDWARE]
        participant OP as Opérateur<br/>(Pilote à distance)<br/>[HUMAIN]
    end

    Note over CAPTEURS,MEDIA: Boucle continue à 30-60 FPS pour la vidéo<br/>et 48 kHz pour l'audio

    CAPTEURS->>MEDIA: flux vidéo brut (matrice de pixels RGB)<br/>flux audio brut (PCM 48 kHz)

    MEDIA->>MEDIA: encodage vidéo (H.264 ou VP8)<br/>encodage audio (Opus)
    MEDIA->>MEDIA: adaptation du bitrate<br/>selon la qualité réseau

    MEDIA->>LK: publish video track<br/>publish audio track

    Note over LK: LiveKit distribue les tracks<br/>à tous les participants abonnés

    LK-->>WEBXR: forward video track<br/>forward audio track

    WEBXR->>WEBXR: décodage vidéo<br/>décodage audio
    WEBXR->>QUEST: rendu stéréo dans les écrans<br/>diffusion audio dans les écouteurs
    QUEST->>OP: l'opérateur voit et entend<br/>l'environnement du robot

    Note over MEDIA,WEBXR: Latence cible end-to-end : sous 150 ms<br/>(capture → affichage)

    loop Flux continu pendant toute la session
        CAPTEURS->>MEDIA: frame suivante
        MEDIA->>LK: publish (en continu)
        LK-->>WEBXR: forward (en continu)
        WEBXR->>QUEST: rendu (en continu)
    end

    Note over LK: En cas de dégradation réseau :<br/>LiveKit baisse automatiquement la résolution<br/>avant de couper (Simulcast)
```
````

---

## Comment lire ce diagramme

**Les boîtes colorées (`box rgb(...)`)** regroupent les acteurs par macro-zone :
- 🟢 Vert clair : tout ce qui est physiquement dans le robot (capteurs et LiveKit Room côté cloud)
- 🟣 Violet pâle : le Cerveau du robot (logiciel embarqué)
- 🔵 Bleu clair : le poste du pilote

**Les flèches solides (`->>`)** = appel direct
**Les flèches pointillées (`-->>`)** = retour ou diffusion asynchrone (LiveKit forwarde aux abonnés)
**Les `loop`** = action qui se répète en continu
**Les `Note over`** = informations contextuelles importantes (latence, comportement réseau)

**À retenir** : c'est un flux **purement descendant** (du robot vers l'opérateur), continu, avec adaptation automatique de la qualité.

---
