import json
import os
import time

import jwt


def parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_livekit_keys():
    keys_str = os.getenv("LIVEKIT_KEYS", "")
    if not keys_str or ":" not in keys_str:
        raise RuntimeError("La variable LIVEKIT_KEYS est introuvable ou mal formatee.")

    api_key, api_secret, *_ = keys_str.split(":")
    api_key = api_key.replace('"', "").replace("'", "").strip()
    api_secret = api_secret.replace('"', "").replace("'", "").strip()

    if not api_key or not api_secret:
        raise RuntimeError("La variable LIVEKIT_KEYS est introuvable ou mal formatee.")

    return api_key, api_secret


def build_video_grant(role, room_name):
    if role == "publisher":
        grant = {
            "room": room_name,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": parse_bool(os.getenv("LIVEKIT_CAN_SUBSCRIBE"), False),
            "canPublishData": True,
        }

        sources = os.getenv("LIVEKIT_CAN_PUBLISH_SOURCES", "camera")
        if sources:
            grant["canPublishSources"] = [
                source.strip() for source in sources.split(",") if source.strip()
            ]

        return grant

    return {
        "room": room_name,
        "roomJoin": True,
        "canPublish": parse_bool(os.getenv("LIVEKIT_CAN_PUBLISH"), False),
        "canSubscribe": parse_bool(os.getenv("LIVEKIT_CAN_SUBSCRIBE"), True),
        "canPublishData": parse_bool(os.getenv("LIVEKIT_CAN_PUBLISH_DATA"), True),
    }


def main():
    api_key, api_secret = parse_livekit_keys()

    room_name = os.getenv("DEFAULT_ROOM_NAME", "oscar-lot1-room")
    role = os.getenv("LIVEKIT_ROLE", "viewer").strip().lower()
    identity = os.getenv(
        "LIVEKIT_IDENTITY",
        "robot-isaac-sim" if role == "publisher" else "test-front-user",
    )
    name = os.getenv(
        "LIVEKIT_NAME",
        "Isaac Sim Robot" if role == "publisher" else "Developpeur Frontend",
    )
    server_url = os.getenv("LIVEKIT_SERVER_URL", "wss://stream-livekit.oscar-bot.com/")
    ttl_seconds = int(os.getenv("LIVEKIT_TOKEN_TTL_SECONDS", str(31536000)))

    default_metadata = {
        "source": "isaac-sim",
        "robot": "unitree-g1",
        "projection": "flat",
        "layout": "mono",
    } if role == "publisher" else {
        "role": "operator-viewer",
        "app": "oscar",
    }

    metadata = os.getenv("LIVEKIT_METADATA")
    metadata_payload = metadata if metadata else json.dumps(default_metadata)

    now = int(time.time())
    payload = {
        "iss": api_key,
        "sub": identity,
        "name": name,
        "nbf": now,
        "exp": now + ttl_seconds,
        "video": build_video_grant(role, room_name),
        "metadata": metadata_payload,
    }

    token = jwt.encode(payload, api_secret, algorithm="HS256")

    contract = {
        "livekit": {
            "serverUrl": server_url,
            "roomName": room_name,
            "identity": identity,
            "role": role,
            "token": token,
        },
        "mediaContract": {
            "videoTracks": int(os.getenv("MEDIA_VIDEO_TRACKS", "1")),
            "audioTracks": int(os.getenv("MEDIA_AUDIO_TRACKS", "0" if role == "publisher" else "1")),
            "projection": os.getenv("MEDIA_PROJECTION", "flat"),
            "layout": os.getenv("MEDIA_LAYOUT", "mono"),
        },
    }

    print(json.dumps(contract, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Erreur critique : {exc}")
        raise SystemExit(1)
