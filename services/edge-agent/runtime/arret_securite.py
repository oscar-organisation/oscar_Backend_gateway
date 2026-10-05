#!/usr/bin/env python3
"""Arret de securite du chassis, independant du runtime OSCAR.

Le garde-fou de 300 ms de l'agent de commande vit dans le processus qu'il
surveille : si cet agent meurt, ou si son conteneur est arrete pendant un
deplacement, plus personne ne publie de vitesse nulle, et une carte moteur
qui garde sa derniere consigne continue de rouler.

Ce noeud tourne dans le conteneur des pilotes, qui survit au runtime. Il
ecoute la consigne de vitesse et, si elle se tait plus longtemps que le
delai apres une consigne non nulle, publie une vitesse nulle. Il ne publie
rien tant que le robot est a l'arret : il ne dispute la consigne a personne.
"""

from __future__ import annotations

import argparse
import logging
import time

logger = logging.getLogger("oscar.arret_securite")

# Nombre de vitesses nulles envoyees a chaque arret : une seule peut se perdre
# en UDP, et la carte moteur ne la redemande pas.
REPETITIONS = 3


def est_nulle(vx: float, vy: float, wz: float) -> bool:
    return abs(vx) < 1e-6 and abs(vy) < 1e-6 and abs(wz) < 1e-6


class Veille:
    """Decide quand imposer l'arret, sans rien savoir de ROS (testable seul)."""

    def __init__(self, silence_s: float) -> None:
        self.silence_s = silence_s
        self.en_mouvement = False
        self.derniere = 0.0

    def consigne(self, vx: float, vy: float, wz: float, maintenant: float) -> None:
        self.derniere = maintenant
        self.en_mouvement = not est_nulle(vx, vy, wz)

    def doit_arreter(self, maintenant: float) -> bool:
        if self.en_mouvement and maintenant - self.derniere > self.silence_s:
            # Une seule fois par silence : la vitesse nulle publiee revient par
            # l'abonnement et remet l'etat a l'arret.
            self.en_mouvement = False
            return True
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--topic", default="/cmd_vel")
    parser.add_argument("--silence-ms", type=int, default=300)
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    import rclpy
    from geometry_msgs.msg import Twist
    from rclpy.executors import ExternalShutdownException

    rclpy.init()
    noeud = rclpy.create_node("oscar_arret_securite")
    veille = Veille(options.silence_ms / 1000.0)
    sortie = noeud.create_publisher(Twist, options.topic, 10)

    def recevoir(msg: Twist) -> None:
        veille.consigne(msg.linear.x, msg.linear.y, msg.angular.z, time.monotonic())

    def surveiller() -> None:
        if veille.doit_arreter(time.monotonic()):
            logger.warning("consigne muette depuis plus de %d ms : arret impose",
                           options.silence_ms)
            for _ in range(REPETITIONS):
                sortie.publish(Twist())

    noeud.create_subscription(Twist, options.topic, recevoir, 10)
    # Verification quatre fois par delai : l'arret tombe au plus tard a 1,25
    # fois le delai annonce.
    noeud.create_timer(options.silence_ms / 4000.0, surveiller)
    logger.info("arret de securite actif sur %s (%d ms)", options.topic, options.silence_ms)
    try:
        rclpy.spin(noeud)
    except (KeyboardInterrupt, ExternalShutdownException):
        # Arret demande (docker stop) : rclpy a deja ferme le contexte.
        pass
    finally:
        noeud.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
