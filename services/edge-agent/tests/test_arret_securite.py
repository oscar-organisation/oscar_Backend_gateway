import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from arret_securite import Veille  # noqa: E402


class VeilleTest(unittest.TestCase):
    def test_un_silence_apres_un_mouvement_impose_l_arret(self) -> None:
        veille = Veille(0.3)
        veille.consigne(0.2, 0.0, 0.0, maintenant=10.0)
        self.assertFalse(veille.doit_arreter(10.29))
        self.assertTrue(veille.doit_arreter(10.31))

    def test_l_arret_n_est_impose_qu_une_fois_par_silence(self) -> None:
        veille = Veille(0.3)
        veille.consigne(0.0, 0.0, 0.5, maintenant=0.0)
        self.assertTrue(veille.doit_arreter(1.0))
        self.assertFalse(veille.doit_arreter(2.0))

    def test_un_robot_a_l_arret_ne_recoit_rien(self) -> None:
        veille = Veille(0.3)
        veille.consigne(0.0, 0.0, 0.0, maintenant=0.0)
        self.assertFalse(veille.doit_arreter(60.0))
        self.assertFalse(Veille(0.3).doit_arreter(60.0))

    def test_des_consignes_regulieres_ne_declenchent_rien(self) -> None:
        veille = Veille(0.3)
        for pas in range(100):
            instant = pas / 30.0
            veille.consigne(0.3, 0.0, 0.0, maintenant=instant)
            self.assertFalse(veille.doit_arreter(instant + 0.01))


if __name__ == "__main__":
    unittest.main()
