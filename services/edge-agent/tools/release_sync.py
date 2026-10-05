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
RELEASE_ENV_PAR_DEFAUT = Path("/etc/oscar/release.env")
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


def installer(dossier_release, timeout=900.0, mettre_en_service=True):
    # type: (Path, float, bool) -> Tuple[int, str]
    """Depose une release, et ne la met en service que si on le demande.

    Deux passes, volontairement : la premiere pose les fichiers sans toucher
    a /opt/oscar/current, ce qui laisse le temps de verifier que l'image
    correspondante existe ; la seconde installe outils et unites et fait
    basculer. Sans cette separation, une image absente du registre laissait le
    robot avec un lien deja deplace vers une version qu'il ne pouvait pas
    demarrer.
    """
    commande = ["bash", str(dossier_release / "scripts" / "install.sh")]
    if not mettre_en_service:
        commande.append("--no-switch")
    return executer(commande, timeout=timeout)


def reference_image(racine, version, config):
    # type: (Path, str, Path) -> str
    """Image attendue par une release installee.

    Trois sources se rejoignent ici, et la separation est voulue : la release
    nomme le depot, le profil du robot nomme la famille de chassis, et son
    fichier de configuration nomme le registre. Le meme paquet vise ainsi un
    registre de preproduction sans etre reconstruit.

    Le profil entre dans le nom parce qu'une version donnee du paquet ne
    produit pas une image mais une par famille de chassis : celle d'un
    ROSMASTER porte la base ROS du constructeur, celle d'un autre chassis en
    porte une autre. Sans ce suffixe, la seconde ecraserait la premiere sous
    le meme nom.
    """
    profil_env = lire_env(config)
    registre = profil_env.get("OSCAR_REGISTRY", "").strip()
    famille = profil_env.get("OSCAR_ROBOT_PROFILE", "").strip()
    if not registre or not famille:
        return ""
    fichier = racine / "releases" / version / "IMAGE"
    try:
        depot = fichier.read_text(encoding="utf-8").strip()
    except OSError:
        depot = ""
    depot = depot or "oscar/edge"
    # Depuis 0.6.0 : l'image est designee par son empreinte et ne depend plus
    # de la famille, les pilotes du chassis vivant dans l'image constructeur.
    try:
        empreinte = (racine / "releases" / version / "IMAGE_DIGEST").read_text(
            encoding="utf-8").strip()
    except OSError:
        empreinte = ""
    if empreinte:
        return "%s/%s@%s" % (registre, depot, empreinte)
    return "%s/%s-%s:%s" % (registre, depot, famille, version)


def verifier_signature(racine, version, image, timeout=300.0):
    # type: (Path, str, str, float) -> Tuple[int, str]
    """Refuse une image dont la signature ne se verifie pas.

    Une release qui livre une cle publique exige une image signee par la
    cle privee correspondante. Les releases plus anciennes n'en livrent pas
    et passent, faute de quoi aucun retour vers elles ne serait possible.
    """
    dossier = racine / "releases" / version
    cle = dossier / "config" / "cosign.pub"
    if not cle.exists():
        return 0, "release sans cle de signature"
    return executer([str(dossier / "scripts" / "verify-image.sh"), image, str(cle)],
                    timeout=timeout)


def poser_release_env(racine, version, config, chemin=None):
    # type: (Path, str, Path, Optional[Path]) -> None
    """Ecrit la reference d'image correspondant a la release en service.

    Appele a chaque bascule, retour arriere compris : le fichier decrit
    toujours ce vers quoi pointe /opt/oscar/current, jamais autre chose.
    """
    chemin = chemin or RELEASE_ENV_PAR_DEFAUT
    image = reference_image(racine, version, config)
    if not image:
        return
    contenu = (
        "# Ecrit par oscar-release-sync a chaque bascule. Ne pas editer :\n"
        "# toute modification est perdue a la prochaine montee de version.\n"
        "OSCAR_EDGE_VERSION=%s\n"
        "OSCAR_EDGE_IMAGE=%s\n" % (version, image)
    )
    chemin.write_text(contenu, encoding="utf-8")


def tirer_image(image, timeout=1800.0):
    # type: (str, float) -> Tuple[int, str]
    """Tire l'image depuis le registre, sauf si elle est deja sur le disque.

    Une image absente du registre condamne la release : mieux vaut le savoir
    avant de deplacer le lien que devant un conteneur qui ne demarre pas.
    """
    code, _ = executer(["docker", "image", "inspect", image], timeout=60.0)
    if code == 0:
        return 0, "image deja presente"
    return executer(["docker", "pull", image], timeout=timeout)


def basculer(racine, version, config=None, release_env=None):
    # type: (Path, str, Optional[Path], Optional[Path]) -> None
    cible = racine / "releases" / version
    lien = racine / "current"
    temporaire = racine / "current.nouveau"
    if temporaire.is_symlink() or temporaire.exists():
        temporaire.unlink()
    temporaire.symlink_to(cible)
    temporaire.replace(lien)
    if config is not None:
        poser_release_env(racine, version, config, release_env)


def reconcilier(options):
    # type: (argparse.Namespace) -> int
    profil = lire_env(options.config)
    robot = profil.get("OSCAR_ROBOT_ID", "")
    famille = profil.get("OSCAR_ROBOT_PROFILE", "")
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
        _rendre_compte(racine_api, robot, cle, installee, "failed", motif, profil=famille)
        return 65

    dossier_temporaire = Path(tempfile.mkdtemp(prefix="oscar-release-"))
    try:
        archive = dossier_temporaire / ("oscar-edge-%s.tar.gz" % version)
        telecharger("%s/studio/runtime/robots/%s/release/archive" % (racine_api, robot), cle, archive)
        obtenue = empreinte_fichier(archive)
        if not hmac.compare_digest(obtenue, str(release.get("sha256"))):
            motif = "empreinte de l'archive telechargee differente de celle publiee"
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "failed", motif, profil=famille)
            return 65

        dossier_release = extraire(archive, dossier_temporaire)
        code, sortie = installer(dossier_release, mettre_en_service=False)
        if code != 0:
            motif = "installation refusee : %s" % sortie[-300:]
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "failed", motif, profil=famille)
            return 70

        # L'image se tire avant la bascule. Un registre injoignable ou une
        # version jamais poussee laisse alors le robot exactement ou il etait,
        # au lieu de le laisser devant un conteneur qui ne demarrera pas.
        image = reference_image(options.root, version, options.config)
        if not image:
            code, sortie = 78, ("OSCAR_REGISTRY ou OSCAR_ROBOT_PROFILE absent de %s"
                                % options.config)
        else:
            code, sortie = tirer_image(image)
        if code != 0:
            motif = "image %s indisponible : %s" % (image or "?", sortie[-200:])
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "failed", motif, profil=famille)
            return 69

        code, sortie = verifier_signature(options.root, version, image)
        if code != 0:
            motif = "signature de %s refusee : %s" % (image, sortie[-200:])
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "failed", motif, profil=famille)
            return 69

        # L'image est la : on peut mettre la release en service.
        code, sortie = installer(dossier_release)
        if code != 0:
            motif = "mise en service refusee : %s" % sortie[-300:]
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "failed", motif, profil=famille)
            return 70
        basculer(options.root, version, options.config, options.release_env)
        code, sortie = executer(["/usr/local/libexec/oscar-preflight"], timeout=300.0)
        if code != 0 and installee:
            # Retour arriere : la version precedente est encore sur le disque,
            # c'est tout l'interet de ne jamais ecraser une release.
            basculer(options.root, installee, options.config, options.release_env)
            executer(["systemctl", "restart", "oscar-edge.service"])
            motif = "prevol en echec sur %s, retour a %s" % (version, installee)
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, installee, "rolled_back", motif, profil=famille)
            return 75
        if code != 0:
            motif = "prevol en echec sur %s et aucune version precedente" % version
            logger.error(motif)
            _rendre_compte(racine_api, robot, cle, version, "failed", motif, profil=famille)
            return 70

        if not options.no_restart:
            executer(["systemctl", "restart", "oscar-edge.service"])
        logger.info("version %s installee", version)
        _rendre_compte(racine_api, robot, cle, version, "installed",
                       "installee depuis %s" % (installee or "aucune"), release.get("sha256"),
                       profil=famille)
        return 0
    finally:
        shutil.rmtree(str(dossier_temporaire), ignore_errors=True)


def _rendre_compte(racine_api, robot, cle, version, statut, message, sha256=None, profil=None):
    # type: (str, str, str, str, str, str, Optional[str], Optional[str]) -> None
    corps = {"version": version, "statut": statut, "message": message[:500]}
    if sha256:
        corps["sha256"] = sha256
    if profil:
        # Le robot est la seule source qui sache sur quel chassis il tourne.
        # La console enregistre cette declaration a cote de ce que l'operateur
        # a saisi, et montre l'ecart au lieu de le masquer.
        corps["profil"] = profil
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
    analyseur.add_argument("--release-env", type=Path, default=RELEASE_ENV_PAR_DEFAUT)
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
