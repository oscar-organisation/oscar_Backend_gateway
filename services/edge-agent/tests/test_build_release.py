import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


class BuildReleaseTest(unittest.TestCase):
    """L'archive designe son image par empreinte, ou n'est pas fabriquee."""

    def _construire(self, env):
        with tempfile.TemporaryDirectory() as copie:
            subprocess.run(["cp", "-a", str(RACINE) + "/.", copie], check=True)
            resultat = subprocess.run(
                [copie + "/scripts/build-release.sh"], capture_output=True, text=True,
                env={**os.environ, **env})
            archives = list(Path(copie, "dist").glob("oscar-edge-*.tar.gz"))
            membres = []
            if resultat.returncode == 0:
                version = Path(copie, "VERSION").read_text().strip()
                archive = Path(copie, "dist", "oscar-edge-%s.tar.gz" % version)
                with tarfile.open(archive) as tar:
                    membres = {m.name.split("/", 1)[-1]: m for m in tar.getmembers()}
                    if "IMAGE_DIGEST" in membres:
                        membres["IMAGE_DIGEST"] = tar.extractfile(membres["IMAGE_DIGEST"]).read().decode()
            return resultat.returncode, membres, archives

    def test_sans_empreinte_l_archive_est_refusee(self) -> None:
        code, _, _ = self._construire({"OSCAR_EDGE_DIGEST": ""})
        self.assertNotEqual(code, 0)

    def test_une_empreinte_invalide_est_refusee(self) -> None:
        code, _, _ = self._construire({"OSCAR_EDGE_DIGEST": "sha256:court"})
        self.assertNotEqual(code, 0)

    def test_l_archive_porte_l_empreinte_l_arret_et_la_cle(self) -> None:
        empreinte = "sha256:" + "b" * 64
        code, membres, _ = self._construire({"OSCAR_EDGE_DIGEST": empreinte})
        self.assertEqual(code, 0)
        self.assertEqual(membres["IMAGE_DIGEST"].strip(), empreinte)
        for chemin in ("runtime/arret_securite.py", "docker/chassis.sh",
                       "docker/healthcheck-chassis.sh", "config/cosign.pub",
                       "scripts/verify-image.sh", "systemd/oscar-chassis.service"):
            self.assertIn(chemin, membres)
        self.assertNotIn("compose.build.yaml", membres)


if __name__ == "__main__":
    unittest.main()
