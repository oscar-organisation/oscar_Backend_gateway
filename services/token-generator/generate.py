import os
import time
import json
import jwt

# Extraction securisee des cles issues du fichier d'environnement
keys_str = os.getenv('LIVEKIT_KEYS', '')
api_key = ''
api_secret = ''

if keys_str:
    parts = keys_str.split(':')
    if len(parts) >= 2:
        api_key = parts[0].replace('"', '').replace("'", "").strip()
        api_secret = parts[1].replace('"', '').replace("'", "").strip()

if not api_key or not api_secret:
    print("Erreur critique : La variable LIVEKIT_KEYS est introuvable ou mal formatee.")
    exit(1)

room_name = os.getenv('DEFAULT_ROOM_NAME', 'oscar-lot1-room')

# Constitution de la payload Jwt pour LiveKit (validite de 1 annee pour le developpement)
payload = {
    "iss": api_key,
    "sub": "test-front-user",
    "name": "Developpeur Frontend",
    "nbf": int(time.time()),
    "exp": int(time.time()) + 31536000,
    "video": {
        "room": room_name,
        "roomJoin": True
    }
}

token = jwt.encode(payload, api_secret, algorithm="HS256")

contract = {
    "livekit": {
        "serverUrl": "ws://127.0.0.1:7880",
        "roomName": room_name,
        "token": token
    },
    "mediaContract": {
        "videoTracks": 1,
        "audioTracks": 1
    }
}

print(json.dumps(contract, indent=2))
