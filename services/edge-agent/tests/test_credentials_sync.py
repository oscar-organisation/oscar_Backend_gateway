"""Renouvellement local des identifiants LiveKit du robot."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "credentials_sync.py"
SPEC = importlib.util.spec_from_file_location("credentials_sync", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def jeton(expiration: int, identifiant: str) -> str:
    def encoder(valeur: dict) -> str:
        brut = json.dumps(valeur, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(brut).decode("ascii").rstrip("=")

    return "%s.%s.signature" % (
        encoder({"alg": "HS256", "typ": "JWT"}),
        encoder({"exp": expiration, "sub": identifiant}),
    )


def identifiant(expiration: int, role: str, variante: str = "initial") -> dict:
    suffixe = "" if role == "media" else "-command"
    return {
        "livekit": {
            "serverUrl": "wss://stream.example.test",
            "roomName": "room-oscar-01",
            "identity": "robot-oscar-01%s" % suffixe,
            "token": jeton(expiration, "%s-%s" % (role, variante)),
        }
    }


class RenouvellementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        racine = Path(self.temp.name)
        self.config = racine / "robot.env"
        self.key = racine / "agent.key"
        self.media = racine / "media.json"
        self.command = racine / "command.json"
        self.state = racine / "credentials-applied.json"
        self.config.write_text(
            "OSCAR_ROBOT_ID=oscar-01\nOSCAR_API_URL=https://console.test/api\n",
            encoding="utf-8",
        )
        self.key.write_text("cle-agent-de-test\n", encoding="utf-8")
        self.maintenant = int(time.time())
        self._recuperer = MODULE.recuperer
        self._redemarrer = MODULE.redemarrer_runtime
        self._ecrire = MODULE.ecrire_json_atomique
        self.reponse = {}
        self.redemarrages = 0

        def recuperer(base, robot, cle):
            self.assertEqual(base, "https://console.test/api")
            self.assertEqual(robot, "oscar-01")
            self.assertEqual(cle, "cle-agent-de-test")
            return self.reponse

        def redemarrer():
            self.redemarrages += 1
            return True, "runtime redemarre"

        MODULE.recuperer = recuperer
        MODULE.redemarrer_runtime = redemarrer

    def tearDown(self) -> None:
        MODULE.recuperer = self._recuperer
        MODULE.redemarrer_runtime = self._redemarrer
        MODULE.ecrire_json_atomique = self._ecrire
        self.temp.cleanup()

    def options(self):
        return MODULE.construire_arguments([
            "--config", str(self.config),
            "--key-file", str(self.key),
            "--media-file", str(self.media),
            "--command-file", str(self.command),
            "--state-file", str(self.state),
        ])

    def ecrire_identifiants(self, expiration: int, variante: str = "initial") -> None:
        self.media.write_text(json.dumps(identifiant(expiration, "media", variante)), encoding="utf-8")
        self.command.write_text(json.dumps(identifiant(expiration, "command", variante)), encoding="utf-8")

    def reponse_avec(self, expiration: int, variante: str = "nouveau") -> dict:
        return {
            "fichiers": {
                "/etc/oscar/credentials/media.json": identifiant(expiration, "media", variante),
                "/etc/oscar/credentials/command.json": identifiant(expiration, "command", variante),
            }
        }

    def test_des_identifiants_proches_de_lexpiration_sont_renouveles(self) -> None:
        self.ecrire_identifiants(self.maintenant + 2 * 24 * 3600)
        self.reponse = self.reponse_avec(self.maintenant + 30 * 24 * 3600)

        self.assertEqual(MODULE.reconcilier(self.options()), 0)

        self.assertEqual(json.loads(self.media.read_text(encoding="utf-8")),
                         self.reponse["fichiers"]["/etc/oscar/credentials/media.json"])
        self.assertEqual(json.loads(self.command.read_text(encoding="utf-8")),
                         self.reponse["fichiers"]["/etc/oscar/credentials/command.json"])
        self.assertEqual(self.redemarrages, 1)
        self.assertEqual(os.stat(str(self.media)).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(str(self.command)).st_mode & 0o777, 0o600)

    def test_des_identifiants_valides_restent_inchanges(self) -> None:
        self.ecrire_identifiants(self.maintenant + 30 * 24 * 3600)
        os.chmod(str(self.media), 0o644)
        avant_media = self.media.read_bytes()
        avant_command = self.command.read_bytes()
        MODULE.recuperer = lambda *args: self.fail("la console ne doit pas etre appelee")

        self.assertEqual(MODULE.reconcilier(self.options()), 0)

        self.assertEqual(self.media.read_bytes(), avant_media)
        self.assertEqual(self.command.read_bytes(), avant_command)
        self.assertEqual(os.stat(str(self.media)).st_mode & 0o777, 0o600)
        self.assertEqual(self.redemarrages, 0)

    def test_une_console_injoignable_conserve_les_fichiers(self) -> None:
        self.ecrire_identifiants(self.maintenant + 24 * 3600)
        avant_media = self.media.read_bytes()
        avant_command = self.command.read_bytes()

        def indisponible(*args):
            raise urllib.error.URLError("console indisponible")

        MODULE.recuperer = indisponible
        self.assertEqual(MODULE.reconcilier(self.options()), 0)
        self.assertEqual(self.media.read_bytes(), avant_media)
        self.assertEqual(self.command.read_bytes(), avant_command)
        self.assertEqual(self.redemarrages, 0)

    def test_un_fichier_absent_est_recree(self) -> None:
        self.command.write_text(
            json.dumps(identifiant(self.maintenant + 30 * 24 * 3600, "command")),
            encoding="utf-8",
        )
        self.reponse = self.reponse_avec(self.maintenant + 30 * 24 * 3600)
        self.reponse["fichiers"]["/etc/oscar/credentials/command.json"] = json.loads(
            self.command.read_text(encoding="utf-8"))

        self.assertEqual(MODULE.reconcilier(self.options()), 0)

        self.assertTrue(self.media.exists())
        self.assertEqual(os.stat(str(self.media)).st_mode & 0o777, 0o600)
        self.assertEqual(self.redemarrages, 1)

    def test_une_reponse_identique_ne_reecrit_aucun_identifiant(self) -> None:
        self.ecrire_identifiants(self.maintenant + 24 * 3600)
        self.reponse = {
            "fichiers": {
                "/etc/oscar/credentials/media.json": json.loads(self.media.read_text(encoding="utf-8")),
                "/etc/oscar/credentials/command.json": json.loads(self.command.read_text(encoding="utf-8")),
            }
        }
        ecritures = []

        def surveiller(chemin, contenu, mode=0o600):
            if chemin in (self.media, self.command):
                ecritures.append(chemin)
            return self._ecrire(chemin, contenu, mode)

        MODULE.ecrire_json_atomique = surveiller
        self.assertEqual(MODULE.reconcilier(self.options()), 0)
        self.assertEqual(ecritures, [])
        self.assertEqual(self.redemarrages, 0)


if __name__ == "__main__":
    unittest.main()
