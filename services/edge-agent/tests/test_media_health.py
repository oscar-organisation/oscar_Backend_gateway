"""Preuve de publication media et verdict du controle de sante."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock


EDGE_ROOT = Path(__file__).parents[1]
PUBLISHER_PATH = EDGE_ROOT / "runtime" / "livekit_publisher.py"
HEALTHCHECK_PATH = EDGE_ROOT / "docker" / "healthcheck-container.sh"


def charger_publisher():
    """Charge le module sans exiger les dependances natives du conteneur."""
    numpy = types.ModuleType("numpy")
    livekit = types.ModuleType("livekit")
    livekit.rtc = types.SimpleNamespace()
    nom_module = "livekit_publisher_test"
    specification = importlib.util.spec_from_file_location(nom_module, PUBLISHER_PATH)
    module = importlib.util.module_from_spec(specification)
    with mock.patch.dict(
        sys.modules,
        {"numpy": numpy, "livekit": livekit, nom_module: module},
    ):
        assert specification and specification.loader
        specification.loader.exec_module(module)
        return module


PUBLISHER = charger_publisher()


class TemoinPublicationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.temoin = Path(self.temp.name) / "run" / "media.beat"
        self.publisher = object.__new__(PUBLISHER.LiveKitPublisher)
        self.publisher._temoin = self.temoin

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_battre_ecrit_un_temuin_date(self) -> None:
        with mock.patch.object(PUBLISHER.time, "time", return_value=1_234_567_890):
            self.publisher._battre()
        self.assertEqual(self.temoin.read_text(encoding="utf-8"), "1234567890")

    def test_une_ecriture_impossible_ne_coupe_pas_la_publication(self) -> None:
        self.publisher._temoin = Path(self.temp.name)
        self.publisher._battre()


class ControleSanteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name)
        self.bin = self.racine / "bin"
        self.bin.mkdir()
        self.temoin = self.racine / "media.beat"
        self._outil("pgrep", "#!/bin/sh\nexit 0\n")
        self._outil(
            "stat",
            "#!%s\nimport os, sys\nprint(int(os.stat(sys.argv[-1]).st_mtime))\n" % sys.executable,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _outil(self, nom: str, contenu: str) -> None:
        chemin = self.bin / nom
        chemin.write_text(contenu, encoding="utf-8")
        chemin.chmod(0o755)

    def executer(self) -> subprocess.CompletedProcess[str]:
        environnement = dict(os.environ)
        environnement.update({
            "PATH": "%s:%s" % (self.bin, environnement["PATH"]),
            "OSCAR_ENABLE_MEDIA": "true",
            "OSCAR_ENABLE_COMMAND": "false",
            "OSCAR_BRINGUP_COUNT": "0",
            "OSCAR_MEDIA_HEARTBEAT": str(self.temoin),
            "OSCAR_MEDIA_HEARTBEAT_MAX_AGE": "45",
        })
        return subprocess.run(
            ["bash", str(HEALTHCHECK_PATH)],
            env=environnement,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

    def test_un_temoin_recent_prouve_la_publication(self) -> None:
        self.temoin.write_text(str(int(time.time())), encoding="utf-8")
        self.assertEqual(self.executer().returncode, 0)

    def test_un_temoin_absent_signale_un_robot_muet(self) -> None:
        resultat = self.executer()
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("aucune publication", resultat.stderr)

    def test_un_temoin_ancien_signale_un_robot_muet(self) -> None:
        self.temoin.write_text("ancien", encoding="utf-8")
        ancien = time.time() - 60
        os.utime(self.temoin, (ancien, ancien))
        resultat = self.executer()
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("publication arretee", resultat.stderr)


if __name__ == "__main__":
    unittest.main()
