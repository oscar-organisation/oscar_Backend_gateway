"""Mise a jour du paquet embarque : verification, installation, retour arriere."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "release_sync.py"
SPEC = importlib.util.spec_from_file_location("release_sync", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def archive_valide(chemin: Path, version: str = "1.0.0") -> None:
    with tarfile.open(str(chemin), "w:gz") as tar:
        for nom, contenu in ((f"oscar-edge-{version}/VERSION", version.encode()),
                             (f"oscar-edge-{version}/scripts/install.sh", b"#!/bin/bash\nexit 0\n")):
            info = tarfile.TarInfo(nom)
            info.size = len(contenu)
            tar.addfile(info, io.BytesIO(contenu))


class SignatureTest(unittest.TestCase):
    def test_la_signature_se_recalcule_a_partir_de_la_cle(self) -> None:
        cle = "cle-de-test"
        empreinte = hashlib.sha256(b"archive").hexdigest()
        attendu = hmac.new(
            hashlib.sha256(cle.encode()).hexdigest().encode(), empreinte.encode(), hashlib.sha256,
        ).hexdigest()
        self.assertEqual(MODULE.signature_attendue(empreinte, cle), attendu)

    def test_une_cle_differente_donne_une_autre_signature(self) -> None:
        empreinte = hashlib.sha256(b"archive").hexdigest()
        self.assertNotEqual(MODULE.signature_attendue(empreinte, "cle-a"),
                            MODULE.signature_attendue(empreinte, "cle-b"))


class ExtractionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.dossier = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_une_archive_normale_donne_sa_racine(self) -> None:
        archive = self.dossier / "paquet.tar.gz"
        archive_valide(archive, "1.2.3")
        racine = MODULE.extraire(archive, self.dossier / "sortie")
        self.assertEqual(racine.name, "oscar-edge-1.2.3")

    def test_une_archive_qui_sort_du_dossier_est_refusee(self) -> None:
        """Un chemin remontant écraserait des fichiers du système."""
        archive = self.dossier / "piege.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            info = tarfile.TarInfo("../evasion")
            info.size = 3
            tar.addfile(info, io.BytesIO(b"mal"))
        (self.dossier / "sortie").mkdir()
        with self.assertRaises(RuntimeError):
            MODULE.extraire(archive, self.dossier / "sortie")

    def test_une_archive_a_plusieurs_racines_est_refusee(self) -> None:
        archive = self.dossier / "double.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            for nom in ("un/VERSION", "deux/VERSION"):
                info = tarfile.TarInfo(nom)
                info.size = 1
                tar.addfile(info, io.BytesIO(b"1"))
        with self.assertRaises(RuntimeError):
            MODULE.extraire(archive, self.dossier / "sortie")


class BasculeTest(unittest.TestCase):
    """Le lien « current » est ce qui rend la bascule et le retour instantanes."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name)
        for version in ("1.0.0", "1.1.0"):
            dossier = self.racine / "releases" / version
            dossier.mkdir(parents=True)
            (dossier / "VERSION").write_text(version, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_basculer_puis_revenir(self) -> None:
        MODULE.basculer(self.racine, "1.0.0")
        self.assertEqual(MODULE.version_installee(self.racine), "1.0.0")
        MODULE.basculer(self.racine, "1.1.0")
        self.assertEqual(MODULE.version_installee(self.racine), "1.1.0")
        MODULE.basculer(self.racine, "1.0.0")
        self.assertEqual(MODULE.version_installee(self.racine), "1.0.0")

    def test_la_version_precedente_reste_sur_le_disque(self) -> None:
        MODULE.basculer(self.racine, "1.1.0")
        self.assertTrue((self.racine / "releases" / "1.0.0" / "VERSION").exists())


class CycleTest(unittest.TestCase):
    """Cycle complet avec une console simulée."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        racine = Path(self.temp.name)
        self.config = racine / "robot.env"
        self.config.write_text(
            "OSCAR_ROBOT_ID=oscar-02\nOSCAR_API_URL=https://console.test/api\n", encoding="utf-8")
        self.cle_fichier = racine / "agent.key"
        self.cle_fichier.write_text("cle-de-test\n", encoding="utf-8")
        self.root = racine / "opt"
        (self.root / "releases" / "1.0.0").mkdir(parents=True)
        (self.root / "releases" / "1.0.0" / "VERSION").write_text("1.0.0", encoding="utf-8")
        MODULE.basculer(self.root, "1.0.0")

        self.archive_source = racine / "source.tar.gz"
        archive_valide(self.archive_source, "1.1.0")
        self.sha = MODULE.empreinte_fichier(self.archive_source)
        self.comptes_rendus: list[dict] = []
        self.installations: list[Path] = []
        self.commandes: list[list[str]] = []

        self._appel = MODULE._appel
        self._telecharger = MODULE.telecharger
        self._installer = MODULE.installer
        self._executer = MODULE.executer

        def appel(url, cle, corps=None, timeout=30.0):
            if corps is not None:
                self.comptes_rendus.append(corps)
                return {}
            return {"canal": "stable", "installee": "1.0.0", "release": {
                "version": "1.1.0", "sha256": self.sha, "taille": 10, "notes": "",
                "empreinte_signee": MODULE.signature_attendue(self.sha, "cle-de-test"),
            }}

        MODULE._appel = appel
        MODULE.telecharger = lambda url, cle, destination, timeout=600.0: destination.write_bytes(
            self.archive_source.read_bytes())
        MODULE.installer = lambda dossier, timeout=900.0: (
            self.installations.append(dossier) or self._preparer(dossier) or (0, ""))
        MODULE.executer = lambda commande, timeout=600.0: (
            self.commandes.append(commande) or (self.code_prevol, "sortie"))
        self.code_prevol = 0

    def _preparer(self, dossier: Path) -> None:
        """Simule ce que fait install.sh : poser la release sous son numero."""
        cible = self.root / "releases" / "1.1.0"
        cible.mkdir(parents=True, exist_ok=True)
        (cible / "VERSION").write_text("1.1.0", encoding="utf-8")

    def tearDown(self) -> None:
        MODULE._appel = self._appel
        MODULE.telecharger = self._telecharger
        MODULE.installer = self._installer
        MODULE.executer = self._executer
        self.temp.cleanup()

    def _options(self):
        return MODULE.construire_arguments([
            "--config", str(self.config), "--key-file", str(self.cle_fichier),
            "--root", str(self.root), "--no-restart",
        ])

    def test_une_version_valide_sinstalle_et_est_declaree(self) -> None:
        self.assertEqual(MODULE.reconcilier(self._options()), 0)
        self.assertEqual(MODULE.version_installee(self.root), "1.1.0")
        self.assertEqual(self.comptes_rendus[-1]["statut"], "installed")
        self.assertEqual(self.comptes_rendus[-1]["version"], "1.1.0")

    def test_un_prevol_en_echec_ramene_la_version_precedente(self) -> None:
        self.code_prevol = 1
        code = MODULE.reconcilier(self._options())
        self.assertEqual(code, 75)
        self.assertEqual(MODULE.version_installee(self.root), "1.0.0")
        self.assertEqual(self.comptes_rendus[-1]["statut"], "rolled_back")

    def test_une_empreinte_non_signee_refuse_le_telechargement(self) -> None:
        """L'archive n'est meme pas demandee : le refus vient avant."""
        appels = {"telechargements": 0}

        def telecharger(url, cle, destination, timeout=600.0):
            appels["telechargements"] += 1

        MODULE.telecharger = telecharger
        MODULE._appel = lambda url, cle, corps=None, timeout=30.0: (
            self.comptes_rendus.append(corps) or {} if corps is not None else
            {"canal": "stable", "installee": "1.0.0", "release": {
                "version": "1.1.0", "sha256": self.sha, "taille": 10,
                "empreinte_signee": "0" * 64}})
        self.assertEqual(MODULE.reconcilier(self._options()), 65)
        self.assertEqual(appels["telechargements"], 0)
        self.assertEqual(self.comptes_rendus[-1]["statut"], "failed")

    def test_une_archive_alteree_est_refusee(self) -> None:
        MODULE.telecharger = lambda url, cle, destination, timeout=600.0: destination.write_bytes(
            b"archive remplacee en chemin")
        self.assertEqual(MODULE.reconcilier(self._options()), 65)
        self.assertEqual(MODULE.version_installee(self.root), "1.0.0")

    def test_une_console_injoignable_laisse_la_version_en_place(self) -> None:
        def tombe(url, cle, corps=None, timeout=30.0):
            raise TimeoutError("console muette")

        MODULE._appel = tombe
        self.assertEqual(MODULE.reconcilier(self._options()), 0)
        self.assertEqual(MODULE.version_installee(self.root), "1.0.0")


if __name__ == "__main__":
    unittest.main()
