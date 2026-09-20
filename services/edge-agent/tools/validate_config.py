#!/usr/bin/env python3
"""Validate an OSCAR Edge configuration without exposing credentials."""


import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROBOT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")


def read_env(path):
    # type: (Path) -> Dict[str, str]
    values = {}  # type: Dict[str, str]
    for line_number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: ligne invalide")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def decode_jwt_claims(token):
    # type: (str) -> dict
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("JWT mal forme")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("payload JWT illisible") from exc


def read_token_file(path):
    # type: (Path) -> Tuple[dict, dict]
    data = json.loads(path.read_text())
    livekit = data.get("livekit")
    if not isinstance(livekit, dict):
        raise ValueError("objet livekit absent")
    for key in ("serverUrl", "roomName", "identity", "token"):
        if not livekit.get(key):
            raise ValueError(f"livekit.{key} absent")
    return livekit, decode_jwt_claims(str(livekit["token"]))


def validate(env_path, media_path, command_path, now=None):
    # type: (Path, Path, Path, Optional[int]) -> List[str]
    errors = []  # type: List[str]
    now = now or int(time.time())

    try:
        env = read_env(env_path)
    except Exception as exc:  # noqa: BLE001
        return [f"configuration illisible: {exc}"]

    robot_id = env.get("OSCAR_ROBOT_ID", "")
    if not ROBOT_ID_PATTERN.fullmatch(robot_id):
        errors.append("OSCAR_ROBOT_ID doit etre un identifiant canonique en minuscules")
    if not env.get("ROBOT_BASE_IMAGE") or env.get("ROBOT_BASE_IMAGE", "").startswith("CHANGE_ME"):
        errors.append("ROBOT_BASE_IMAGE doit designer l'image ROS du constructeur")

    integer_limits = {
        "OSCAR_CAMERA_WIDTH": (160, 4096),
        "OSCAR_CAMERA_HEIGHT": (120, 2160),
        "OSCAR_CAMERA_FPS": (1, 60),
        "OSCAR_WATCHDOG_MS": (100, 1000),
        "OSCAR_CONTROL_HZ": (5, 100),
    }
    for key, (minimum, maximum) in integer_limits.items():
        try:
            value = int(env.get(key, ""))
            if not minimum <= value <= maximum:
                raise ValueError
        except ValueError:
            errors.append(f"{key} doit etre compris entre {minimum} et {maximum}")

    credentials = {}  # type: Dict[str, Tuple[dict, dict]]
    for role, path in (("media", media_path), ("command", command_path)):
        try:
            credentials[role] = read_token_file(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"credential {role} invalide: {exc}")

    if len(credentials) == 2:
        media, media_claims = credentials["media"]
        command, command_claims = credentials["command"]
        if media["roomName"] != command["roomName"]:
            errors.append("les agents media et commande ne ciblent pas la meme room")
        if media["serverUrl"] != command["serverUrl"]:
            errors.append("les agents media et commande ne ciblent pas le meme serveur")
        if media["identity"] == command["identity"]:
            errors.append("les identites LiveKit media et commande doivent etre distinctes")

        for role, claims in (("media", media_claims), ("command", command_claims)):
            expiry = claims.get("exp")
            if not isinstance(expiry, (int, float)) or expiry <= now + 300:
                errors.append(f"JWT {role} expire ou expire dans moins de cinq minutes")
            room = claims.get("video", {}).get("room")
            if room != credentials[role][0]["roomName"]:
                errors.append(f"JWT {role}: room incoherente")

        media_grants = media_claims.get("video", {})
        command_grants = command_claims.get("video", {})
        if not media_grants.get("canPublish"):
            errors.append("JWT media sans droit canPublish")
        if not command_grants.get("canSubscribe") or not command_grants.get("canPublishData"):
            errors.append("JWT commande sans canSubscribe/canPublishData")

    return errors


def main():
    # type: () -> int
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--media-token", type=Path, required=True)
    parser.add_argument("--command-token", type=Path, required=True)
    args = parser.parse_args()

    errors = validate(args.env, args.media_token, args.command_token)
    if errors:
        for error in errors:
            print(f"[ERREUR] {error}", file=sys.stderr)
        return 1
    print("[OK] configuration et credentials coherents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
