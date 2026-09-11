from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "validate_config.py"
SPEC = importlib.util.spec_from_file_location("validate_config", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def token(claims: dict) -> str:
    def encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode({'alg': 'HS256'})}.{encode(claims)}.signature"


class ValidateConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.env = root / "robot.env"
        self.media = root / "media.json"
        self.command = root / "command.json"
        self.env.write_text(
            "\n".join(
                (
                    "OSCAR_ROBOT_ID=oscar-02",
                    "ROBOT_BASE_IMAGE=vendor/m3pro:humble",
                    "OSCAR_CAMERA_WIDTH=640",
                    "OSCAR_CAMERA_HEIGHT=480",
                    "OSCAR_CAMERA_FPS=30",
                    "OSCAR_WATCHDOG_MS=300",
                    "OSCAR_CONTROL_HZ=30",
                )
            )
        )
        base = {"exp": 2_000_000_000, "video": {"room": "room-02", "roomJoin": True}}
        self._write_token(self.media, "robot-oscar-02", {**base["video"], "canPublish": True})
        self._write_token(
            self.command,
            "robot-oscar-02-command",
            {**base["video"], "canSubscribe": True, "canPublishData": True},
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _write_token(path: Path, identity: str, video: dict) -> None:
        livekit_token = token({"exp": 2_000_000_000, "video": video})
        path.write_text(
            json.dumps(
                {
                    "livekit": {
                        "serverUrl": "wss://stream.example.test",
                        "roomName": "room-02",
                        "identity": identity,
                        "token": livekit_token,
                    }
                }
            )
        )

    def test_accepts_consistent_configuration(self) -> None:
        self.assertEqual(MODULE.validate(self.env, self.media, self.command, now=1_900_000_000), [])

    def test_rejects_cross_room_credentials(self) -> None:
        data = json.loads(self.command.read_text())
        data["livekit"]["roomName"] = "other-room"
        self.command.write_text(json.dumps(data))
        errors = MODULE.validate(self.env, self.media, self.command, now=1_900_000_000)
        self.assertTrue(any("meme room" in error for error in errors))

    def test_rejects_expired_credentials(self) -> None:
        for path in (self.media, self.command):
            data = json.loads(path.read_text())
            claims = decode_claims(data["livekit"]["token"])
            claims["exp"] = 100
            data["livekit"]["token"] = token(claims)
            path.write_text(json.dumps(data))
        errors = MODULE.validate(self.env, self.media, self.command, now=1_000)
        self.assertEqual(sum("expire" in error for error in errors), 2)


def decode_claims(value: str) -> dict:
    payload = value.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


if __name__ == "__main__":
    unittest.main()
