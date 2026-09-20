"""Reconciliation d'un bundle sur le robot : projection, refus, idempotence."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "bundle_sync.py"
SPEC = importlib.util.spec_from_file_location("bundle_sync", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


PROFIL = {
    "OSCAR_ROBOT_ID": "oscar-01",
    "OSCAR_CAMERA_TOPIC": "/camera/color/image_raw",
    "OSCAR_CMD_VEL_TOPIC": "/cmd_vel",
}


def agent(code: str, *, video: bool = False, audio: bool = False, entrees: bool = False,
          type_entree: str = "TYPE_ENTREE_ABONNEMENT_TEMPS_REEL") -> dict:
    return {
        "code": code,
        "publie_video": video,
        "publie_audio": audio,
        "entrees": [{"code": "CANAL_RECEPTION", "type": type_entree, "format": "BINAIRE_COMPACT"}] if entrees else [],
        "sorties": [],
    }


def charge(composants: list[dict], *, checksum: str | None = None, version: int = 3) -> dict:
    resultat = {
        "format": "oscar.bundle.runtime.v1",
        "robot": "oscar-01",
        "deployment": {"id": "d1", "statut": "delivered", "bundle": "robot-magasin",
                       "version": version, "checksum": checksum},
        "manifest": {
            "bundle": {"code": "BUNDLE_DEPLOIEMENT_MAGASIN", "nom": "Robot magasin",
                       "cible": "ENVIRONNEMENT_EXECUTION_ROBOT"},
            "composants": composants,
            "liaisons": [],
        },
    }
    resultat["deployment"]["checksum"] = checksum or MODULE.hashlib.sha256(
        json.dumps(resultat["manifest"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return resultat


class ProjectionTest(unittest.TestCase):
    def test_un_agent_video_active_le_media(self) -> None:
        projection, ignores, refus = MODULE.projeter(
            charge([{"code": "INSTANCE_SERVICE_MEDIA", "cible": "ENVIRONNEMENT_EXECUTION_ROBOT",
                     "agents": [agent("CAMERA_AVANT", video=True)]}]), PROFIL)
        self.assertEqual(refus, [])
        self.assertEqual(ignores, [])
        self.assertEqual(projection["OSCAR_ENABLE_MEDIA"], "true")
        self.assertEqual(projection["OSCAR_ENABLE_COMMAND"], "false")
        self.assertEqual(projection["OSCAR_BUNDLE_VERSION"], "3")

    def test_un_composant_web_est_ignore_sans_faire_echouer(self) -> None:
        """Une composition décrit aussi la télécommande : elle se déploie ailleurs."""
        projection, ignores, refus = MODULE.projeter(
            charge([
                {"code": "INSTANCE_SERVICE_ACTIONS", "cible": "ENVIRONNEMENT_EXECUTION_ROBOT",
                 "agents": [agent("PILOTAGE", entrees=True)]},
                {"code": "INSTANCE_APPLICATION_TELECOMMANDE",
                 "cible": "ENVIRONNEMENT_EXECUTION_NAVIGATEUR_WEB",
                 "agents": [agent("OPERATEUR", entrees=True)]},
            ]), PROFIL)
        self.assertEqual(refus, [])
        self.assertEqual(ignores, ["INSTANCE_APPLICATION_TELECOMMANDE (ENVIRONNEMENT_EXECUTION_NAVIGATEUR_WEB)"])
        self.assertEqual(projection["OSCAR_ENABLE_COMMAND"], "true")
        self.assertEqual(projection["OSCAR_BUNDLE_AGENTS"], "PILOTAGE")

    def test_un_abonnement_ros2_nest_pas_une_reception_de_commandes(self) -> None:
        """La caméra s'abonne à un topic ROS : ça ne démarre pas l'agent de commande."""
        projection, _, refus = MODULE.projeter(
            charge([{"code": "INSTANCE_SERVICE_MEDIA", "cible": "ENVIRONNEMENT_EXECUTION_ROBOT",
                     "agents": [agent("CAMERA_AVANT", video=True, entrees=True,
                                      type_entree="TYPE_ENTREE_ABONNEMENT_ROS_2")]}]), PROFIL)
        self.assertEqual(refus, [])
        self.assertEqual(projection["OSCAR_ENABLE_MEDIA"], "true")
        self.assertEqual(projection["OSCAR_ENABLE_COMMAND"], "false")

    def test_une_capacite_non_fournie_est_refusee_plutot_qu_ignoree(self) -> None:
        _, _, refus = MODULE.projeter(
            charge([{"code": "INSTANCE_SERVICE_MEDIA", "cible": "ENVIRONNEMENT_EXECUTION_ROBOT",
                     "agents": [agent("MICRO", audio=True, video=True)]}]), PROFIL)
        self.assertTrue(any("audio" in motif for motif in refus))

    def test_un_profil_sans_camera_refuse_une_publication_video(self) -> None:
        _, _, refus = MODULE.projeter(
            charge([{"code": "INSTANCE_SERVICE_MEDIA", "cible": "ENVIRONNEMENT_EXECUTION_ROBOT",
                     "agents": [agent("CAMERA_AVANT", video=True)]}]),
            {"OSCAR_ROBOT_ID": "oscar-01", "OSCAR_CMD_VEL_TOPIC": "/cmd_vel"})
        self.assertTrue(any("OSCAR_CAMERA_TOPIC" in motif for motif in refus))

    def test_un_agent_sans_role_est_refuse(self) -> None:
        _, _, refus = MODULE.projeter(
            charge([{"code": "INSTANCE_SERVICE_VIDE", "cible": "ENVIRONNEMENT_EXECUTION_ROBOT",
                     "agents": [agent("INERTE")]}]), PROFIL)
        self.assertTrue(any("aucun role" in motif for motif in refus))

    def test_un_format_de_manifeste_inconnu_est_refuse(self) -> None:
        _, _, refus = MODULE.projeter({"format": "oscar.bundle.runtime.v9"}, PROFIL)
        self.assertTrue(any("format" in motif for motif in refus))

    def test_composition_sans_agent_robot_est_refusee(self) -> None:
        _, _, refus = MODULE.projeter(charge([]), PROFIL)
        self.assertTrue(any("aucun agent" in motif for motif in refus))


class ApplicationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env = Path(self.temp.name) / "bundle.env"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_une_configuration_identique_ne_redemarre_pas_le_runtime(self) -> None:
        """Un redémarrage inutile coupe la vidéo : on compare avant d'agir."""
        projection = {"OSCAR_ENABLE_MEDIA": "true", "OSCAR_BUNDLE_VERSION": "3"}
        change, _ = MODULE.appliquer(projection, self.env, redemarrer=False)
        self.assertTrue(change)
        change, detail = MODULE.appliquer(projection, self.env, redemarrer=False)
        self.assertFalse(change)
        self.assertIn("inchangee", detail)

    def test_le_rendu_est_stable_quel_que_soit_lordre(self) -> None:
        a = MODULE.rendu_env({"B": "2", "A": "1"})
        b = MODULE.rendu_env({"A": "1", "B": "2"})
        self.assertEqual(a, b)

    def test_le_fichier_genere_annonce_quil_est_genere(self) -> None:
        MODULE.appliquer({"OSCAR_ENABLE_MEDIA": "true"}, self.env, redemarrer=False)
        self.assertIn("genere par oscar-bundle-sync", self.env.read_text(encoding="utf-8"))


class RuntimeNonSuperviseTest(unittest.TestCase):
    """Une partie du parc tourne encore sans le paquet embarque."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env = Path(self.temp.name) / "bundle.env"
        self._executer = MODULE.executer
        MODULE.executer = lambda commande, timeout=300.0: (4, "Unit oscar-edge.service could not be found.")

    def tearDown(self) -> None:
        MODULE.executer = self._executer
        self.temp.cleanup()

    def test_une_unite_installee_mais_inactive_ne_compte_pas(self) -> None:
        """Installer la release pose l'unité bien avant qu'on ne bascule dessus."""
        reponses = {"is-active": (3, "inactive"), "is-enabled": (1, "disabled")}
        MODULE.executer = lambda commande, timeout=300.0: reponses.get(commande[1], (0, ""))
        self.assertFalse(MODULE.runtime_supervise())

    def test_une_unite_active_compte(self) -> None:
        MODULE.executer = lambda commande, timeout=300.0: (0, "active")
        self.assertTrue(MODULE.runtime_supervise())

    def test_la_configuration_est_deposee_et_le_dit(self) -> None:
        change, detail = MODULE.appliquer({"OSCAR_ENABLE_MEDIA": "true"}, self.env, redemarrer=True)
        self.assertTrue(change)
        self.assertIn("non supervise", detail)
        self.assertTrue(self.env.exists())


class EnvTest(unittest.TestCase):
    def test_lecture_dun_profil_avec_commentaires_et_guillemets(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "robot.env"
            chemin.write_text('# commentaire\nOSCAR_ROBOT_ID="oscar-01"\nVIDE\n', encoding="utf-8")
            valeurs = MODULE.lire_env(chemin)
        self.assertEqual(valeurs, {"OSCAR_ROBOT_ID": "oscar-01"})

    def test_un_etat_illisible_ne_fait_pas_echouer_la_lecture(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "etat.json"
            chemin.write_text("{ pas du json", encoding="utf-8")
            self.assertEqual(MODULE.lire_etat(chemin), {})


class CycleTest(unittest.TestCase):
    """Cycle complet avec une console simulée, sans réseau ni systemd."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        racine = Path(self.temp.name)
        self.config = racine / "robot.env"
        self.config.write_text(
            "OSCAR_ROBOT_ID=oscar-01\n"
            "OSCAR_API_URL=https://api.example.test/api\n"
            "OSCAR_CAMERA_TOPIC=/camera/color/image_raw\n"
            "OSCAR_CMD_VEL_TOPIC=/cmd_vel\n",
            encoding="utf-8",
        )
        self.cle = racine / "agent.key"
        self.cle.write_text("cle-de-test\n", encoding="utf-8")
        self.env = racine / "bundle.env"
        self.etat = racine / "applied.json"
        self.comptes_rendus: list[dict] = []
        self.reponse = charge([{"code": "INSTANCE_SERVICE_MEDIA",
                                "cible": "ENVIRONNEMENT_EXECUTION_ROBOT",
                                "agents": [agent("CAMERA_AVANT", video=True)]}])

        self._recuperer = MODULE.recuperer
        self._rendre_compte = MODULE.rendre_compte
        MODULE.recuperer = lambda base, robot, cle: self.reponse
        MODULE.rendre_compte = lambda base, robot, cle, corps: self.comptes_rendus.append(corps) or {}

    def tearDown(self) -> None:
        MODULE.recuperer = self._recuperer
        MODULE.rendre_compte = self._rendre_compte
        self.temp.cleanup()

    def _options(self, **extra):
        return MODULE.construire_arguments([
            "--config", str(self.config), "--key-file", str(self.cle),
            "--env-file", str(self.env), "--state-file", str(self.etat),
            "--no-restart", *[str(item) for item in extra.get("args", [])],
        ])

    def test_sans_redemarrage_la_configuration_est_preparee_pas_active(self) -> None:
        code = MODULE.reconcilier(self._options())
        self.assertEqual(code, 0)
        self.assertEqual(len(self.comptes_rendus), 1)
        compte = self.comptes_rendus[0]
        self.assertEqual(compte["statut"], "prepared")
        self.assertEqual(compte["checksum"], self.reponse["deployment"]["checksum"])
        self.assertIn("OSCAR_ENABLE_MEDIA=true", self.env.read_text(encoding="utf-8"))
        # La trace locale permet de repartir apres une coupure reseau.
        self.assertEqual(json.loads(self.etat.read_text(encoding="utf-8"))["statut"], "prepared")

    def test_une_version_deja_preparee_nest_pas_reappliquee(self) -> None:
        MODULE.reconcilier(self._options())
        self.reponse["deployment"]["statut"] = "prepared"
        code = MODULE.reconcilier(self._options())
        self.assertEqual(code, 0)
        self.assertEqual(len(self.comptes_rendus), 1)

    def test_un_manifeste_altere_ne_touche_pas_la_configuration(self) -> None:
        self.reponse["manifest"]["bundle"]["nom"] = "alteration"
        self.assertEqual(MODULE.reconcilier(self._options()), 65)
        self.assertFalse(self.env.exists())
        self.assertEqual(self.comptes_rendus, [])

    def test_un_nouveau_deploiement_identique_recoit_son_propre_rapport(self) -> None:
        MODULE.reconcilier(self._options())
        self.reponse["deployment"].update(id="d2", statut="prepared")
        self.assertEqual(MODULE.reconcilier(self._options()), 0)
        self.assertEqual(self.comptes_rendus[-1]["deployment_id"], "d2")

    def test_un_diagnostic_absent_ne_prouve_pas_la_sante(self) -> None:
        self.assertFalse(MODULE.verifier_sante(str(Path(self.temp.name) / "absent"))[0])

    def test_un_hote_sans_runtime_supervise_ne_reecrit_pas_son_compte_rendu(self) -> None:
        """La minuterie repasse toutes les 45 s : elle ne doit pas rejouer le meme verdict."""
        executer_reel = MODULE.executer
        MODULE.executer = lambda commande, timeout=300.0: (4, "Unit oscar-edge.service could not be found.")
        try:
            options = MODULE.construire_arguments([
                "--config", str(self.config), "--key-file", str(self.cle),
                "--env-file", str(self.env), "--state-file", str(self.etat),
            ])
            MODULE.reconcilier(options)
            self.assertEqual(self.comptes_rendus[-1]["statut"], "prepared")
            self.reponse["deployment"]["statut"] = "prepared"
            MODULE.reconcilier(options)
            self.assertEqual(len(self.comptes_rendus), 1)
        finally:
            MODULE.executer = executer_reel

    def test_une_composition_inapplicable_est_declaree_en_echec(self) -> None:
        self.reponse = charge([{"code": "INSTANCE_SERVICE_MEDIA",
                                "cible": "ENVIRONNEMENT_EXECUTION_ROBOT",
                                "agents": [agent("MICRO", audio=True, video=True)]}])
        code = MODULE.reconcilier(self._options())
        self.assertEqual(code, 65)
        self.assertEqual(self.comptes_rendus[0]["statut"], "failed")
        self.assertFalse(self.env.exists())

    def test_une_console_injoignable_laisse_le_robot_en_place(self) -> None:
        def tombe(base, robot, cle):
            raise TimeoutError("console muette")

        MODULE.recuperer = tombe
        self.assertEqual(MODULE.reconcilier(self._options()), 0)
        self.assertFalse(self.env.exists())
        self.assertEqual(self.comptes_rendus, [])


if __name__ == "__main__":
    unittest.main()
