# ==============================================================================
# Simulateur Média Avancé (Robot Publisher via OpenCV & Native WebRTC)
# ==============================================================================
# PRÉSENTATION ARCHITECTURALE :
# Ce composant Python remplace une implémentation réseau "GStreamer/WHIP" stricte
# pour une raison matérielle simple : le greffon expérimental "whipsink" n'est 
# pas packagé en standard sur les distributions Linux actuelles (Ubuntu 24).
# 
# D'un point de vue industriel I.A., utiliser OpenCV (qui s'appuie lui-même 
# silencieusement sur GStreamer pour capturer l'USB) et le SDK natif LiveKit 
# (écrit en Rust) est la vraie solution de production pour les robots sous Python.
# Cela garantit une portabilité matérielle absolue sur n'importe quel OS.
# ==============================================================================

import os
import asyncio
import cv2
import numpy as np
import time
from livekit import api, rtc
import jwt

async def generate_token(api_key: str, api_secret: str, room_name: str) -> str:
    """
    Génère un ticket d'entrée crypto-signé (Local JWT) pour s'authentifier
    auprès du point d'accès réseau LiveKit. Exactement comme le ferait un vrai 
    Robot autonome en démarrage à froid.
    """
    payload = {
        "iss": api_key,                  # Identité de l'émetteur configuré dans le Cloud
        "sub": "robot-simulateur",       # Identité interne du conteneur dans la session RTC
        "name": "Caméra Simulateur Robot",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 31536000, # Valide 1 an entier (contexte développeur)
        "video": {
            "room": room_name,           # Le flux sera cantonné à cette salle
            "roomJoin": True,            # Droit de faire acte de présence
            "canPublish": True           # Droit critique : Injecter de la vidéo
        }
    }
    return jwt.encode(payload, api_secret, algorithm="HS256")

async def main():
    # 1. LECTURE DES PARAMÈTRES D'ENVIRONNEMENT
    # Docker injecte le '.env.dev' automatiquement. Le code réagit dynamiquement.
    livekit_url = os.getenv("LIVEKIT_URL", "ws://livekit:7880")
    room_name = os.getenv("DEFAULT_ROOM_NAME", "oscar-lot1-room")
    
    # Isolation et traitement robuste des clés secrètes combinées
    keys_str = os.getenv('LIVEKIT_KEYS', '')
    api_key, api_secret = ("devkey", "devsecret") # Clés de secours
    if ":" in keys_str:
        api_key, api_secret = [k.replace('"', '').replace("'", "").strip() for k in keys_str.split(':')]

    # Configuration des couches matérielles (OpenCV Engine)
    source_type = os.getenv("MEDIA_SOURCE_TYPE", "test_pattern")
    video_path = os.getenv("MEDIA_VIDEO_PATH", "/app/video.mp4")
    # OpenCV interprète les capteurs V4L2 ou USB natifs sous forme d'entiers (ex: /dev/video0 -> 0)
    device_id = int(os.getenv("MEDIA_DEVICE", "0"))

    print("====== DÉMARRAGE DU MOTEUR CAMÉRA (OPENCV / NATIVE RTC) ======")
    print(f"Source active : {source_type}")
    print(f"Serveur cible : {livekit_url}")

    # 2. NÉGOCIATION RÉSEAU DU FLUX
    token = await generate_token(api_key, api_secret, room_name)
    # L'objet Room encapsule toutes les connexions Peer-to-Peer et WebSockets RTC.
    room = rtc.Room()
    
    print("Handshake WebRTC en cours d'initialisation...")
    await room.connect(livekit_url, token)
    print("✅ Handshake réussi. Authentification Serveur OK.")

    # Ouverture du tuayau asynchrone (Pipe) vers LiveKit pour notre vidéo (Passage en HD 720p).
    source = rtc.VideoSource(1280, 720)
    track = rtc.LocalVideoTrack.create_video_track("robot-video", source)
    
    opts = rtc.TrackPublishOptions()
    opts.source = rtc.TrackSource.SOURCE_CAMERA
    await room.local_participant.publish_track(track, opts)
    print("✅ Canal vidéo ouvert et réservé dans la Room virtuelle.")

    # 3. ARMEMENT DU SYSTÈME OPTIQUE (Lecteur Média)
    cap = None
    if source_type == "video_file":
        # Lecture en décodage matériel d'un fichier stocké (MP4 par ex.)
        if os.path.exists(video_path):
            cap = cv2.VideoCapture(video_path)
            print(f"Bande magnétique {video_path} chargée.")
        else:
            print(f"Avertissement: Fichier introuvable. Repli en mode de secours (Mire).")
            source_type = "test_pattern"
    elif source_type == "usb_camera":
        # Capture matérielle native d'une webcam ou d'un flux V4L2 GStreamer
        cap = cv2.VideoCapture(device_id)
        if not cap.isOpened():
            print(f"Erreur E/S: Périphérique /dev/video{device_id} verrouillé. Repli en mode de secours.")
            source_type = "test_pattern"
            cap = None

    print("▶️ Amorçage de la pompe de capture en temps réel (FPS: ~30)...")
    tick = 0
    
    # 4. LA BOUCLE INFINIE DU ROBOT (Inhale les images -> Crache vers le réseau)
    while True:
        frame = None
        
        # [A] Phase d'acquisition (Sensory Input)
        if source_type in ["video_file", "usb_camera"] and cap is not None:
            ret, frame = cap.read()
            if not ret:
                # La vidéo enregistrée arrive à la fin : on simule un live continu en la rembobinant.
                if source_type == "video_file":
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                
                # Si erreur de lecture physique d'interface USB persistante, on attend un cycle CPU
                if not ret:
                    await asyncio.sleep(0.1)
                    continue
            
            # Normalisation dimensionnelle. WebRTC hait les flux vidéo qui changent de taille.
            frame = cv2.resize(frame, (1280, 720))
        else:
            # Mode "Test" : OpenCV dessine littéralement une image vierge avec du texte et des formes géométriques CPU
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(frame, "SCENE IMMERSIVE (Mire HD)", (350, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
            cv2.circle(frame, (640 + int(np.sin(tick/10.0)*300), 150), 45, (0, 255, 0), -1)
            tick += 1

        # [B] Translation spatio-métrique (Color Input)
        # OpenCV traite historiquement la lumière en Bleu-Vert-Rouge (BGR). 
        # Les standards webs (WebRTC) l'exigent en Rouge-Vert-Bleu-Alpha (RGBA).
        rgba_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        
        # [C] Envoi Réseau WebRTC vers l'Ingress du serveur (LiveKit C++)
        # L'objet VideoFrame encapsule le bloc de pixels bruts dans la matrice attendue par WebRTC.
        lk_frame = rtc.VideoFrame(1280, 720, rtc.VideoBufferType.RGBA, rgba_frame.tobytes())
        # Le pont Rust/C++ s'occupe de l'encodage H264 hardware (s'il existe) et de la fragmentation RTP
        source.capture_frame(lk_frame)
        
        # [D] Horloge Biologique du cycle (Pacing)
        # On limite le CPU à 30 frames par secondes (1 seconde / 30 = ~0.033) pour ne pas engorger le réseau.
        await asyncio.sleep(0.033)

if __name__ == "__main__":
    # Trappe d'exécution asynchrone sécurisée
    asyncio.run(main())
