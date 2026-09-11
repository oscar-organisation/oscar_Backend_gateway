
```mermaid
sequenceDiagram

flowchart LR

    %% =========================================
    %% STYLES PAR TYPE DE COMPOSANT
    %% =========================================
    classDef humain fill:#E6F1FB,stroke:#185FA5,stroke-width:1.5px,color:#042C53;
    classDef software fill:#EEEDFE,stroke:#534AB7,stroke-width:1px,color:#26215C;
    classDef hardware fill:#FAEEDA,stroke:#854F0B,stroke-width:1px,color:#412402;
    classDef mixte fill:#FAECE7,stroke:#993C1D,stroke-width:1px,color:#4A1B0C;
    classDef pivot fill:#E1F5EE,stroke:#0F6E56,stroke-width:3px,color:#04342C;

    %% =========================================
    %% MACRO 1 - POSTE DU PILOTE (en haut à gauche)
    %% =========================================
    subgraph POSTE["1 - Poste du pilote à distance"]
        direction TB
        OP["Opérateur<br/>(Pilote à distance)<br/>[HUMAIN]"]
        QUEST["Casque Meta Quest<br/>(Casque de réalité virtuelle)<br/>[HARDWARE]"]
        WEBXR["WebXR / Three.js<br/>(Application VR du pilote)<br/>[SOFTWARE]"]
        OP --> QUEST
        QUEST --> WEBXR
    end

    %% =========================================
    %% MACRO 2 - CERVEAU DU ROBOT (en bas à gauche)
    %% =========================================
    subgraph CERVEAU["2 - Cerveau du robot - Ordinateur embarqué ou Machine virtuelle (Raccorder au robot) <br/>[HARDWARE ou ENVIRONNEMENT VIRTUEL 'ISAAC' ou Autres]"]
        direction TB
        MEDIA["Media Agent<br/>(Module Caméra & Micro)<br/>[SOFTWARE]"]
        STATE["State Publisher (high-level state) <br/>(Module Tableau de bord)<br/>[SOFTWARE]"]
        STATE_POSE_LOW_LATENCE["State Publisher État haute fréquence (low-latency state) : Pose Stream (60-100 Hz) binaire <br/>[SOFTWARE]"]
        GATEWAY["Edge Gateway<br/>(Module Réception ordres (Trie, identifi et confirme les Ordres Recus))<br/>[SOFTWARE]"]
        SAFETY["Safety Supervisor<br/>(Garde-fou sécurité et gestions des limites)<br/>[SOFTWARE]"]
        BRIDGE["Robot Bridge<br/>(Traducteur vers le robot)<br/>[SOFTWARE]"]
        GATEWAY --> SAFETY
        SAFETY --> BRIDGE
    end

    %% =========================================
    %% MACRO 3 - ROBOT (tout en bas)
    %% =========================================
    subgraph ROBOT["3 - Robot physique et simulation"]
        direction TB
        ROS["ROS 2<br/>(Système robot temps réel)<br/>[SOFTWARE]"]
        ISAAC["Isaac Sim<br/>(Robot simulé NVIDIA)<br/>[SOFTWARE]"]
        REAL["Robot réel<br/>(Machine physique)<br/>(Moteurs · actionneurs - autres capteurs du Robot) [SOFTWARE et HARDWARE ROBOT]"]
        CAPTEURS["Capteurs Media<br/>(Caméras · micros · IMU - Haut-parleur)<br/>[HARDWARE] <br/> OU <br/>[HARDWARE VIRTUEL (ISAAC SIM - NVIDIA)] "]
        ROS --> |"Reception des commandes "| ISAAC
        ISAAC --> |"Envoie des etats capteurs et actionneurs "| ROS
        ROS --> |"Reception des commandes "|REAL
        REAL --> |"Envoie des etats capteurs et actionneurs "|ROS
        CAPTEURS --> ROS
    end

    %% =========================================
    %% PIVOT CENTRAL - LIVEKIT
    %% =========================================
    subgraph TEMPS_REEL["LIVEKIT - Pivot temps réel central"]
        LK["LiveKit Room<br/>(Salle virtuelle temps réel)<br/>[SOFTWARE]"]
    end

    %% =========================================
    %% MACRO 4 - IA CLOUD (en haut à droite)
    %% =========================================
    subgraph IA["4 - Couche IA dans le cloud"]
        direction TB
        AIGW["AI Gateway<br/>(Pont vers l'IA)<br/>[SOFTWARE]"]
        MIMICX["MimicX<br/>(Cerveau IA - vision et dialogue)<br/>[SOFTWARE]"]
        AUTONOMY["Autonomy Logic<br/>(Pilote automatique)<br/>[SOFTWARE]"]
        AIGW --> MIMICX
        MIMICX --> AIGW
        AIGW --> AUTONOMY
        AUTONOMY --> AIGW
    end

    %% =========================================
    %% MACRO 5 - CLIENT EN MAGASIN (à droite au milieu)
    %% =========================================
    subgraph MAGASIN["5 - Espace magasin"]
        CLIENT["Client en magasin<br/>(Visiteur du supermarché)<br/>[HUMAIN]"]
    end

    %% =========================================
    %% MACRO 6 - BACKEND (en bas à droite)
    %% =========================================
    subgraph BACK["6 - Backend applicatif"]
        direction TB
        SESSION["Session Service<br/>(Service de connexion)<br/>[SOFTWARE]"]
        REGISTRY["Robot Registry<br/>(Annuaire des robots)<br/>[SOFTWARE]"]
        AUDIT["Audit / Logs<br/>(Journal d'activité)<br/>[SOFTWARE]"]
        SESSION --> REGISTRY
        SESSION --> AUDIT
    end

    %% =========================================
    %% LIAISONS DEPUIS / VERS LIVEKIT (toutes en étoile)
    %% =========================================
    WEBXR ==>|"Envoie audio · commandes - switch mode <br/>(auto & Manual)"| LK
    LK ==> |"Reception <br/>- Media (Video - audio) <br/>- data Overlays video (position mapping 3D de reconnaissance, guide ..etc)  "| WEBXR
    LK ==> |"Reception Etats et capteurs Robot · télémétrie générale Robot (Real-Time)  :Batterie, températures, modes, Liste d'alertes "| WEBXR
    WEBXR ==> |"Envoie télémétrie Operateur Casque VR/AR État haute fréquence (low-latency state) :<br/>- Pose tête (position + orientation);<br/>- Pose mains / bras (si applicable);<br/>- Vitesse linéaire/angulaire instantanée "| LK
    MEDIA ==>|"publie le flux vidéo et audio du robot"| LK
    STATE ==>|"publie la télémétrie du robot (etats, Capteurs ..etc)"| LK
    LK ==>|"transmet les ordres reçus :<br/>- commandes opérateur (téléopération)<br/>- consignes pilote auto (mode autonome)"| GATEWAY
    LK ==>|"Audio et vidéo à analyser "| AIGW
    AIGW ==> |"- Retour Response audio IA "| LK
    AIGW ==> |"- Retour Data overlays renvoyés 3D mapping; <br/>- Retour Data commande autonomes  "| LK
    STATE_POSE_LOW_LATENCE ==>|"publie les etats de Pose du robot en temps reel (Faible latence)"| LK


    %% =========================================
    %% LIAISONS HARDWARE LOCALES ROBOT - CERVEAU
    %% =========================================
    CAPTEURS -->|"flux vidéo brut et audio"| MEDIA
    MEDIA -->|"voix de réponse vers haut-parleur"| CAPTEURS
    ROS -->|"états et capteurs agrégés"| STATE

    BRIDGE -->|"traduit en commandes ROS (standard communication Robot)"| ROS
    ROS -->|"Publish Pose "| STATE_POSE_LOW_LATENCE

    SAFETY -->|"notifications de rejets de commande et clamps"| STATE

    %% =========================================
    %% LIAISON CLIENT MAGASIN
    %% =========================================
    CLIENT -->|"parle via micro du robot"| CAPTEURS
    CAPTEURS -->|"reçoit la voix via le haut-parleur du robot"| CLIENT

    %% =========================================
    %% LIAISON BACKEND
    %% =========================================
    OP <-->|"demande session · reçoit token"| SESSION

    %% =========================================
    %% APPLICATION DES STYLES
    %% =========================================
    class OP,CLIENT humain;
    class QUEST,CAPTEURS hardware;
    class WEBXR,MEDIA,GATEWAY,STATE,STATE_POSE_LOW_LATENCE,SAFETY,BRIDGE,AIGW,MIMICX,AUTONOMY,ROS,ISAAC,SESSION,REGISTRY,AUDIT software;
    class REAL mixte;
    class LK pivot;


```