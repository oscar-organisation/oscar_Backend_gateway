#!/usr/bin/env python3
"""Mise a jour du paquet embarque, tiree depuis la console.

La configuration arrivait deja toute seule ; le code, lui, demandait encore une
copie manuelle sur chaque robot. Ce module ferme cette derniere etape, avec les
garanties qu'exige la distribution d'executable :

- l'archive est verifiee **avant** d'etre installee, contre une empreinte
  transmise a part et signee par la cle propre a ce robot ;
- l'installation ne touche pas la version en service tant que le prevol de la
  nouvelle n'est pas passe ;
- un echec revient a la version precedente tout seul, et le dit.

Le robot garde le dernier mot : c'est lui qui sait si une version demarre.
"""

import argparse
import hashlib
import hmac
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_PAR_DEFAUT = Path("/etc/oscar/robot.env")
CLE_PAR_DEFAUT = Path("/etc/oscar/credentials/agent.key")
RACINE_PAR_DEFAUT = Path("/opt/oscar")

logger = logging.getLogger("oscar-release-sync")


def lire_env(chemin):
    # type: (Path) -> Dict[str, str]
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


def version_installee(racine):
    # type: (Path) -> str
    fichier = racine / "current" / "VERSION"
    try:
        return fichier.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def empreinte_fichier(chemin):
    # type: (Path) -> str
    digest = hashlib.sha256()
    with chemin.open("rb") as flux:
        for morceau in iter(lambda: flux.read(1024 * 1024), b""):
            digest.update(morceau)
    return digest.hexdigest()


def signature_attendue(sha256, cle):
    # type: (str, str) -> str
    """La console signe l'empreinte avec l'empreinte de notre cle.

    Le robot refait le meme calcul : une archive annoncee par quelqu'un qui ne
    connait pas cette cle ne passe pas, meme si son sha256 est coherent.
    """
    empreinte_cle = hashlib.sha256(cle.encode("utf-8")).hexdigest()
    return hmac.new(empreinte_cle.encode("utf-8"), sha256.encode("utf-8"), hashlib.sha256).hexdigest()


def _appel(url, cle, corps=None, timeout=30.0):
    # type: (str, str, Optional[dict], float) -> dict
    donnees = json.dumps(corps).encode("utf-8") if corps is not None else None
    requete = urllib.request.Request(url, data=donnees, method="POST" if corps is not None else "GET")
    requete.add_header("X-Oscar-Agent-Key", cle)
    if donnees is not None:
        requete.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310
        return json.loads(reponse.read().decode("utf-8") or "{}")


def telecharger(url, cle, destination, timeout=600.0):
    # type: (str, str, Path, float) -> None
    requete = urllib.request.Request(url)
    requete.add_header("X-Oscar-Agent-Key", cle)
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310
        with destination.open("wb") as sortie:
            shutil.copyfileobj(reponse, sortie, 1024 * 1024)


def executer(commande, timeout=600.0):
    # type: (List[str], float) -> Tuple[int, str]
    try:
        resultat = subprocess.run(
            commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return 1, str(erreur)
    return resultat.returncode, (resultat.stdout + resultat.stderr).strip()


def extraire(archive, destination):
    # type: (Path, Path) -> Path
    """Extrait l'archive en refusant tout chemin qui sortirait du dossier."""
    with tarfile.open(str(archive), "r:gz") as tar:
        membres = tar.getmembers()
        for membre in membres:
            cible = (destination / membre.name).resolve()
            if not str(cible).startswith(str(destination.resolve())):
                raise RuntimeError("archive refusee : chemin hors du dossier (%s)" % membre.name)
        tar.extractall(str(destination))
    racines = [item for item in destination.iterdir() if item.is_dir()]
    if len(racines) != 1:
        raise RuntimeError("archive refusee : une seule racine attendue")
    return racines[0]


def installer(dossier_release, timeout=900.0):
    # type: (Path, float) -> Tuple[int, str]
    return executer(["bash", str(dossier_release / "scripts" / "install.sh")], timeout=timeout)


def basculer(racine, version):
    # type: (Path, str) -> None
    cible = racine / "releases" / version
    lien = racine / "current"
    temporaire = racine / "current.nouveau"
    if temporaire.is_symlink() or temporaire.exists():
        temporaire.unlink()
    temporaire.symlink_to(cible)
    temporaire.replace(lien)


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

    installee = version_installee(options.root)
    racine_api = base.rstrip("/")
    try:
        vue = _appel("%s/studio/runtime/robots/%s/release?version=%s" % (racine_api, robot, installee), cle)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erreur:
        logger.warning("console injoignable (%s) : la version en place est conservee", erreur)
        return 0

    release = vue.get("release")
    if not release:
        logger.info("version %s a jour sur le canal %s", installee or "?", vue.get("canal"))
        return 0

    version = str(release.get("version"))
    logger.info("nouvelle version proposee : %s (canal %s)", version, vue.get("canal"))

    attendue = signature_attendue(str(release.get("sha256")), cle)
    if not hmac.compare_digest(str(release.get("empreinte_signee") or ""), attendue):
        motif = "empreinte non signee par notre cle : archive refusee sans etre telechargee"
        logger.error(motif)
        _rendre_compte(racine_api, robot, cle, installee, "failed", motif)
        return 65

    dossier_temporaire = Path(tempfile.mkdtemp(prefix="oscar-release-"))
    try:
        archive = dossier_temporaire / ("oscar-edge-%s.tar.gz" % version)
        telecharger("%s/studio/runtime/robots/%s/release/archive" % (racine_api, robot), cle, archive)
        obtenue = empreinte_fichier(archive)
        if not hmac.compare_digest(obtenue, str(release.get("sha256"))):
            motif = "empreinte de l'archive telechargee differente de celle publiee"
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "failed", motif)
            return 65

        dossier_release = extraire(archive, dossier_temporaire)
        code, sortie = installer(dossier_release)
        if code != 0:
            motif = "installation refusee : %s" % sortie[-300:]
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "failed", motif)
            return 70

        basculer(options.root, version)
        code, sortie = executer(["/usr/local/libexec/oscar-preflight"], timeout=300.0)
        if code != 0 and installee:
            # Retour arriere : la version precedente est encore sur le disque,
            # c'est tout l'interet de ne jamais ecraser une release.
            basculer(options.root, installee)
            executer(["systemctl", "restart", "oscar-edge.service"])
            motif = "prevol en echec sur %s, retour a %s" % (version, installee)
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "rolled_back", motif)
            return 75
        if code != 0:
            motif = "prevol en echec sur %s et aucune version precedente" % version
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, version, "failed", motif)
            return 70

        if not options.no_restart:
            executer(["systemctl", "restart", "oscar-edge.service"])
        logger.info("version %s installee", version)
        _rendre_compte(racine_api, robot, cle, version, "installed",
                       "installee depuis %s" % (installee or "aucune"), release.get("sha256"))
        return 0
    finally:
        shutil.rmtree(str(dossier_temporaire), ignore_errors=True)


def _rendre_compte(racine_api, robot, cle, version, statut, message, sha256=None):
    # type: (str, str, str, str, str, str, Optional[str]) -> None
    corps = {"version": version, "statut": statut, "message": message[:500]}
    if sha256:
        corps["sha256"] = sha256
    try:
        _appel("%s/studio/runtime/robots/%s/release/report" % (racine_api, robot), cle, corps)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erreur:
        logger.warning("compte rendu non transmis (%s)", erreur)


def construire_arguments(argv=None):
    # type: (Optional[List[str]]) -> argparse.Namespace
    analyseur = argparse.ArgumentParser(description="Met a jour le paquet embarque depuis la console.")
    analyseur.add_argument("--config", type=Path, default=CONFIG_PAR_DEFAUT)
    analyseur.add_argument("--key-file", type=Path, default=CLE_PAR_DEFAUT)
    analyseur.add_argument("--root", type=Path, default=RACINE_PAR_DEFAUT)
    analyseur.add_argument("--api-url", default="")
    analyseur.add_argument("--no-restart", action="store_true")
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
