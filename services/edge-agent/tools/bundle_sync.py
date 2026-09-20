#!/usr/bin/env python3
"""Reconciliation du bundle publie depuis la console vers ce robot.

Le robot tire sa configuration : aucune connexion entrante n'est necessaire,
ce qui vaut aussi derriere un partage de connexion telephonique ou un Wi-Fi
d'entreprise. Le cycle est volontairement simple et repetable :

    interroger -> projeter -> comparer -> appliquer si besoin -> rendre compte

Partage des roles, qui structure tout le reste : le **bundle** decide de ce qui
tourne (quels agents, quelles capacites), le **profil robot**
(`/etc/oscar/robot.env`) decide de la maniere dont cela se branche sur ce
materiel (topics ROS, limites de vitesse, resolution). Une composition ne
connait pas le cablage d'un chassis, et un chassis n'a pas a connaitre les
intentions d'une flotte.

Quand le bundle reclame une capacite que ce runtime ne fournit pas, la
reconciliation echoue et le dit : appliquer a moitie une composition serait la
pire des reponses, puisque l'operateur l'a composee en connaissance de cause.
"""

import argparse
import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

FORMAT_ATTENDU = "oscar.bundle.runtime.v1"
CIBLE_ROBOT = "ENVIRONNEMENT_EXECUTION_ROBOT"

# Entrees qui font d'un agent un recepteur de commandes distantes. Un
# abonnement ROS 2 ou un service local n'en est pas une : c'est du cablage
# interne au robot, et l'agent de commande n'a alors rien a demarrer.
ENTREES_DE_COMMANDE = frozenset({
    "TYPE_ENTREE_ABONNEMENT_TEMPS_REEL",
    "TYPE_ENTREE_INJECTION_APPLICATION",
})

CONFIG_PAR_DEFAUT = Path("/etc/oscar/robot.env")
CLE_PAR_DEFAUT = Path("/etc/oscar/credentials/agent.key")
ENV_GENERE_PAR_DEFAUT = Path("/etc/oscar/bundle.env")
ETAT_PAR_DEFAUT = Path("/var/lib/oscar/bundle-applied.json")

ENTETE = (
    "# Fichier genere par oscar-bundle-sync : toute modification manuelle sera\n"
    "# ecrasee a la prochaine reconciliation. Le cablage materiel se regle dans\n"
    "# /etc/oscar/robot.env.\n"
)

logger = logging.getLogger("oscar-bundle-sync")


# --------------------------------------------------------------------------- #
#  Lecture de configuration
# --------------------------------------------------------------------------- #
def lire_env(chemin: Path) -> Dict[str, str]:
    """Lit un fichier d'environnement simple (CLE=valeur, # commentaires)."""
    valeurs = {}  # type: Dict[str, str]
    if not chemin.exists():
        return valeurs
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


# --------------------------------------------------------------------------- #
#  Projection du manifeste vers la configuration du runtime
# --------------------------------------------------------------------------- #
def projeter(charge, profil):
    # type: (dict, Dict[str, str]) -> Tuple[Dict[str, str], List[str], List[str]]
    """Traduit un manifeste en variables de runtime.

    Renvoie la projection, les composants ignores (ceux qui ne s'executent pas
    sur un robot) et les refus (capacites reclamees mais non fournies ici).
    """
    refus = []  # type: List[str]
    ignores = []  # type: List[str]

    if charge.get("format") != FORMAT_ATTENDU:
            return {}, [], ["format de manifeste inconnu : %r" % (charge.get("format"),)]

    manifeste = charge.get("manifest") or {}
    deploiement = charge.get("deployment") or {}
    bundle = manifeste.get("bundle") or {}

    media = False
    commande = False
    agents = []  # type: List[str]

    for composant in manifeste.get("composants") or []:
        cible = composant.get("cible") or bundle.get("cible")
        if cible and cible != CIBLE_ROBOT:
            # Une composition decrit aussi la telecommande web ou des services
            # serveur : ils se deploient ailleurs, pas sur ce chassis.
            ignores.append(f"{composant.get('code')} ({cible})")
            continue
        for agent in composant.get("agents") or []:
            code = agent.get("code") or "agent"
            agents.append(code)
            publie_video = bool(agent.get("publie_video"))
            publie_audio = bool(agent.get("publie_audio"))
            recoit = any(
                (canal.get("type") or "") in ENTREES_DE_COMMANDE
                for canal in agent.get("entrees") or []
            )
            consomme = bool(agent.get("entrees"))
            if publie_audio:
                refus.append(f"{code} : publication audio non prise en charge par ce runtime")
            if publie_video:
                media = True
            if recoit:
                commande = True
            if not publie_video and not recoit and not consomme:
                refus.append(f"{code} : aucun role reconnu (ni publication video, ni reception)")

    if media and not profil.get("OSCAR_CAMERA_TOPIC"):
        refus.append("publication video demandee mais OSCAR_CAMERA_TOPIC absent du profil robot")
    if commande and not profil.get("OSCAR_CMD_VEL_TOPIC"):
        refus.append("reception de commandes demandee mais OSCAR_CMD_VEL_TOPIC absent du profil robot")
    if not agents and not refus:
        refus.append("aucun agent a executer sur ce robot dans cette composition")

    projection = {
        "OSCAR_BUNDLE_CODE": str(bundle.get("code") or deploiement.get("bundle") or ""),
        "OSCAR_BUNDLE_VERSION": str(deploiement.get("version") or ""),
        "OSCAR_BUNDLE_CHECKSUM": str(deploiement.get("checksum") or ""),
        "OSCAR_BUNDLE_AGENTS": ",".join(sorted(agents)),
        "OSCAR_ENABLE_MEDIA": "true" if media else "false",
        "OSCAR_ENABLE_COMMAND": "true" if commande else "false",
    }
    return projection, ignores, refus


def rendu_env(projection):
    # type: (Dict[str, str]) -> str
    """Rend la projection sous forme de fichier, dans un ordre stable.

    L'ordre compte : c'est la comparaison du contenu qui decide s'il faut
    redemarrer le runtime, et un redemarrage inutile coupe la video.
    """
    lignes = [f"{cle}={projection[cle]}" for cle in sorted(projection)]
    return ENTETE + "\n".join(lignes) + "\n"


def lire_etat(chemin):
    # type: (Path) -> dict
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def ecrire_fichier(chemin, contenu, mode=0o640):
    # type: (Path, str, int) -> None
    """Ecriture atomique : un fichier a moitie ecrit casserait le demarrage."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(contenu, encoding="utf-8")
    os.chmod(temporaire, mode)
    temporaire.replace(chemin)


# --------------------------------------------------------------------------- #
#  Echanges avec la console
# --------------------------------------------------------------------------- #
def _appel(url, cle, corps=None, timeout=15.0):
    # type: (str, str, Optional[dict], float) -> dict
    donnees = json.dumps(corps).encode("utf-8") if corps is not None else None
    requete = urllib.request.Request(url, data=donnees, method="POST" if corps is not None else "GET")
    requete.add_header("X-Oscar-Agent-Key", cle)
    if donnees is not None:
        requete.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310 (URL de configuration)
        return json.loads(reponse.read().decode("utf-8") or "{}")


def recuperer(base, robot, cle):
    # type: (str, str, str) -> dict
    return _appel(f"{base.rstrip('/')}/studio/runtime/robots/{robot}/bundle", cle)


def rendre_compte(base, robot, cle, corps):
    # type: (str, str, str, dict) -> dict
    return _appel(f"{base.rstrip('/')}/studio/runtime/robots/{robot}/bundle/report", cle, corps)


# --------------------------------------------------------------------------- #
#  Application
# --------------------------------------------------------------------------- #
def executer(commande, timeout=300.0):
    # type: (List[str], float) -> Tuple[int, str]
    try:
        resultat = subprocess.run(
            commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return 1, str(erreur)
    sortie = (resultat.stdout + resultat.stderr).strip()
    return resultat.returncode, sortie


def runtime_supervise(unite="oscar-edge.service"):
    # type: (str) -> bool
    """Le runtime est-il reellement pris en charge par systemd sur cet hote ?

    Une partie du parc tourne encore avec des agents lances a la main, avant le
    paquet embarque. La reconciliation doit rester utile dans cet etat : elle
    depose la configuration et le dit, plutot que d'echouer sur un runtime
    qu'elle ne pilote pas.

    L'existence du fichier d'unite ne suffit pas : installer la release le pose
    sur le disque bien avant qu'on ne bascule. Tant que l'unite n'est ni active
    ni activee au demarrage, le runtime en charge est l'ancien, et un
    diagnostic sur un conteneur absent ne prouverait qu'une chose fausse.
    """
    for verbe in ("is-active", "is-enabled"):
        code, _ = executer(["systemctl", verbe, unite], timeout=20.0)
        if code == 0:
            return True
    return False


def appliquer(projection, env_genere, redemarrer=True):
    # type: (Dict[str, str], Path, bool) -> Tuple[bool, str]
    """Ecrit la configuration et redemarre le runtime si elle a change."""
    contenu = rendu_env(projection)
    ancien = env_genere.read_text(encoding="utf-8") if env_genere.exists() else ""
    if contenu == ancien:
        return False, "configuration inchangee"
    ecrire_fichier(env_genere, contenu)
    if not redemarrer:
        return True, "configuration ecrite (redemarrage non demande)"
    if not runtime_supervise():
        return True, "configuration ecrite ; runtime non supervise par systemd sur cet hote"
    code, sortie = executer(["systemctl", "restart", "oscar-edge.service"])
    if code != 0:
        raise RuntimeError("redemarrage du runtime impossible : %s" % (sortie,))
    return True, "runtime redemarre"


def verifier_sante(chemin="/usr/local/bin/oscar-healthcheck"):
    # type: (str) -> Tuple[bool, str]
    if not Path(chemin).exists():
        return False, "diagnostic indisponible : execution non confirmee"
    code, sortie = executer([chemin, "--quiet"], timeout=120.0)
    return code == 0, sortie or "diagnostic silencieux"


def maintenant():
    # type: () -> str
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
#  Cycle complet
# --------------------------------------------------------------------------- #
def reconcilier(options):
    # type: (argparse.Namespace) -> int
    profil = lire_env(options.config)
    robot = profil.get("OSCAR_ROBOT_ID", "")
    base = options.api_url or profil.get("OSCAR_API_URL", "")
    if not robot or not base:
        logger.error("OSCAR_ROBOT_ID et OSCAR_API_URL sont requis dans %s", options.config)
        return 78
    try:
        cle = options.key_file.read_text(encoding="utf-8").strip()
    except OSError:
        logger.error("cle agent illisible : %s", options.key_file)
        return 78
    if not cle:
        logger.error("cle agent vide : %s", options.key_file)
        return 78

    try:
        charge = recuperer(base, robot, cle)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erreur:
        # Console injoignable : le robot continue de tourner avec ce qu'il a.
        logger.warning("console injoignable (%s) : le runtime en place est conserve", erreur)
        return 0

    deploiement = charge.get("deployment")
    if not deploiement:
        logger.info("aucun deploiement demande pour %s", robot)
        return 0

    canonique = json.dumps(charge.get("manifest") or {}, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False)
    checksum = hashlib.sha256(canonique.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(checksum, str(deploiement.get("checksum") or "")):
        logger.error("empreinte du manifeste invalide : configuration en place conservee")
        return 65

    etat = lire_etat(options.state_file)
    # Sur un hote ou le runtime n'est pas supervise, un passage reussi s'arrete
    # a « prepared » : sans cette equivalence, la minuterie reecrirait le meme
    # compte rendu toutes les 45 secondes.
    verdict_attendu = "prepared" if (options.no_restart or not runtime_supervise()) else "active"
    deja = (
        etat.get("deployment_id") == deploiement.get("id")
        and etat.get("checksum") == deploiement.get("checksum")
        and etat.get("statut") == deploiement.get("statut") == verdict_attendu
    )
    if deja and not options.force:
        logger.info("version %s deja appliquee", deploiement.get("version"))
        return 0

    projection, ignores, refus = projeter(charge, profil)
    if refus:
        motif = " ; ".join(refus)
        logger.error("composition inapplicable : %s", motif)
        _rendre_compte_sur(options, base, robot, cle, deploiement, "failed", motif,
                           {"ignores": ignores, "refus": refus})
        return 65

    try:
        change, detail = appliquer(projection, options.env_file,
                                   redemarrer=not options.no_restart)
    except RuntimeError as erreur:
        _rendre_compte_sur(options, base, robot, cle, deploiement, "failed", str(erreur),
                           {"ignores": ignores})
        return 70

    if options.no_restart or not runtime_supervise():
        sain, diagnostic = True, "configuration preparee uniquement ; execution non confirmee"
        statut = "prepared"
    else:
        sain, diagnostic = verifier_sante()
        statut = "active" if sain else "failed"
    message = detail if sain else f"{detail} ; diagnostic en echec : {diagnostic}"
    _rendre_compte_sur(options, base, robot, cle, deploiement, statut, message, {
        "ignores": ignores,
        "agents": projection["OSCAR_BUNDLE_AGENTS"].split(",") if projection["OSCAR_BUNDLE_AGENTS"] else [],
        "configuration_modifiee": change,
        "diagnostic": diagnostic,
    })
    logger.info("version %s : %s (%s)", deploiement.get("version"), statut, message)
    return 0 if sain else 75


def _rendre_compte_sur(options, base, robot, cle, deploiement, statut, message, rapport):
    # type: (argparse.Namespace, str, str, str, dict, str, str, dict) -> None
    """Rend compte a la console et garde une trace locale du verdict.

    La trace locale sert quand la console n'est pas joignable au moment du
    compte rendu : au prochain passage, l'agent sait ce qu'il a deja applique.
    """
    corps = {
        "deployment_id": deploiement.get("id"),
        "statut": statut,
        "checksum": deploiement.get("checksum"),
        "message": message[:500],
        "report": {**rapport, "edge_version": options.version, "horodatage": maintenant()},
    }
    ecrire_fichier(
        options.state_file,
        json.dumps({
            "deployment_id": deploiement.get("id"),
            "checksum": deploiement.get("checksum"),
            "version": deploiement.get("version"),
            "statut": statut,
            "message": message,
            "horodatage": maintenant(),
        }, ensure_ascii=False, indent=2) + "\n",
        mode=0o644,
    )
    try:
        rendre_compte(base, robot, cle, corps)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erreur:
        logger.warning("compte rendu non transmis (%s) ; il sera rejoue au prochain passage", erreur)


def construire_arguments(argv=None):
    # type: (Optional[List[str]]) -> argparse.Namespace
    analyseur = argparse.ArgumentParser(description="Reconcilie le bundle publie avec ce robot.")
    analyseur.add_argument("--config", type=Path, default=CONFIG_PAR_DEFAUT)
    analyseur.add_argument("--key-file", type=Path, default=CLE_PAR_DEFAUT)
    analyseur.add_argument("--env-file", type=Path, default=ENV_GENERE_PAR_DEFAUT)
    analyseur.add_argument("--state-file", type=Path, default=ETAT_PAR_DEFAUT)
    analyseur.add_argument("--api-url", default="")
    analyseur.add_argument("--version", default=os.environ.get("OSCAR_EDGE_VERSION", "dev"))
    analyseur.add_argument("--force", action="store_true",
                           help="Reapplique meme si la version est deja active.")
    analyseur.add_argument("--no-restart", action="store_true",
                           help="Ecrit la configuration sans redemarrer (verification a blanc).")
    analyseur.add_argument("--log-level", default="INFO")
    return analyseur.parse_args(argv)


def main(argv=None):
    # type: (Optional[List[str]]) -> int
    options = construire_arguments(argv)
    logging.basicConfig(level=options.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return reconcilier(options)


if __name__ == "__main__":
    sys.exit(main())
