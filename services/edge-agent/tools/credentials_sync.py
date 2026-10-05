#!/usr/bin/env python3
"""Renouvelle les identifiants LiveKit du runtime embarque.

Les agents media et commande lisent leur fichier une seule fois, avant leur
appel a ``Room.connect()``. LiveKit recoit ensuite la chaine du JWT, pas son
chemin : remplacer le fichier ne change donc rien au processus deja connecte.
Quand un identifiant change, cet outil redemarre le runtime une seule fois,
apres avoir pose les deux fichiers complets.

Cet outil tourne sur l'hote, avant le conteneur, avec le Python 3.6 du Jetson
Nano historique. Sa syntaxe reste volontairement compatible avec cet
interpreteur.
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


CONFIG_PAR_DEFAUT = Path("/etc/oscar/robot.env")
CLE_PAR_DEFAUT = Path("/etc/oscar/credentials/agent.key")
MEDIA_PAR_DEFAUT = Path("/etc/oscar/credentials/media.json")
COMMANDE_PAR_DEFAUT = Path("/etc/oscar/credentials/command.json")
ETAT_PAR_DEFAUT = Path("/var/lib/oscar/credentials-applied.json")

DESTINATIONS_API = {
    "media": "/etc/oscar/credentials/media.json",
    "command": "/etc/oscar/credentials/command.json",
}

# Sept jours absorbent une semaine de coupure de la console ou du reseau sans
# laisser le robot atteindre l'expiration. Une verification quotidienne garde
# encore six occasions de renouveler avant que la supervision ne soit menacee.
MARGE_JOURS_PAR_DEFAUT = 7.0

logger = logging.getLogger("oscar-credentials-sync")


def lire_env(chemin):
    valeurs = {}
    if not chemin.exists():
        return valeurs
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


def lire_json(chemin):
    try:
        valeur = json.loads(chemin.read_text(encoding="utf-8"))
        return valeur if isinstance(valeur, dict) else None
    except (OSError, ValueError):
        return None


def expiration_jwt(identifiant):
    """Lit ``exp`` sans verifier la signature, qui reste l'affaire de LiveKit.

    Le fichier local appartient a root et sert seulement a decider quand
    redemander un jeton au serveur authentifie. Accepter ici une signature ne
    donnerait aucun droit supplementaire : LiveKit la verifiera a la connexion.
    """
    try:
        token = identifiant["livekit"]["token"]
        morceaux = token.split(".")
        if len(morceaux) != 3:
            return None
        charge = morceaux[1]
        charge += "=" * (-len(charge) % 4)
        donnees = json.loads(base64.urlsafe_b64decode(charge.encode("ascii")).decode("utf-8"))
        expiration = int(donnees["exp"])
        return expiration if expiration > 0 else None
    except (KeyError, TypeError, ValueError, UnicodeError):
        return None


def identifiant_complet(identifiant, maintenant):
    if not isinstance(identifiant, dict):
        return False
    livekit = identifiant.get("livekit")
    if not isinstance(livekit, dict):
        return False
    for champ in ("serverUrl", "roomName", "identity", "token"):
        if not isinstance(livekit.get(champ), str) or not livekit.get(champ):
            return False
    expiration = expiration_jwt(identifiant)
    return expiration is not None and expiration > maintenant


def doit_renouveler(chemin, marge_secondes, maintenant):
    identifiant = lire_json(chemin)
    expiration = expiration_jwt(identifiant) if identifiant is not None else None
    return expiration is None or expiration - maintenant < marge_secondes


def empreinte(identifiant):
    if identifiant is None:
        return ""
    canonique = json.dumps(identifiant, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()


def ecrire_json_atomique(chemin, contenu, mode=0o600):
    """Pose un secret sans jamais exposer un fichier partiellement ecrit."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    descripteur = os.open(str(temporaire), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8") as sortie:
            json.dump(contenu, sortie, ensure_ascii=False, indent=2)
            sortie.write("\n")
            sortie.flush()
            os.fsync(sortie.fileno())
        os.chmod(str(temporaire), mode)
        os.replace(str(temporaire), str(chemin))
    except Exception:
        try:
            temporaire.unlink()
        except OSError:
            pass
        raise


def securiser_permissions(chemin, mode=0o600):
    """Corrige les droits sans reecrire un jeton dont le contenu est stable."""
    try:
        if chemin.exists() and (chemin.stat().st_mode & 0o777) != mode:
            os.chmod(str(chemin), mode)
    except OSError as erreur:
        raise OSError("droits impossibles sur %s : %s" % (chemin, erreur))


def _appel(url, cle, timeout=15.0):
    requete = urllib.request.Request(url)
    requete.add_header("X-Oscar-Agent-Key", cle)
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310
        return json.loads(reponse.read().decode("utf-8") or "{}")


def recuperer(base, robot, cle):
    url = "%s/studio/runtime/robots/%s/credentials" % (base.rstrip("/"), robot)
    return _appel(url, cle)


def extraire_identifiants(reponse, maintenant):
    fichiers = reponse.get("fichiers") if isinstance(reponse, dict) else None
    if not isinstance(fichiers, dict):
        raise ValueError("reponse sans fichiers d'identifiants")
    resultat = {}
    for role, destination in DESTINATIONS_API.items():
        identifiant = fichiers.get(destination)
        if not identifiant_complet(identifiant, maintenant):
            raise ValueError("identifiant %s absent, incomplet ou deja expire" % role)
        resultat[role] = identifiant
    return resultat


def executer(commande, timeout=120.0):
    try:
        resultat = subprocess.run(
            commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return 1, str(erreur)
    return resultat.returncode, (resultat.stdout + resultat.stderr).strip()


def redemarrer_runtime():
    """Recharge les fichiers seulement si systemd pilote un runtime actif."""
    code, _ = executer(["systemctl", "is-active", "--quiet", "oscar-edge.service"], timeout=20.0)
    if code != 0:
        return True, "runtime inactif : les identifiants seront lus au prochain demarrage"
    code, sortie = executer(["systemctl", "restart", "oscar-edge.service"], timeout=300.0)
    if code != 0:
        return False, "redemarrage du runtime impossible : %s" % sortie[-300:]
    return True, "runtime redemarre pour charger les nouveaux identifiants"


def empreintes_courantes(options):
    return {
        "media": empreinte(lire_json(options.media_file)),
        "command": empreinte(lire_json(options.command_file)),
    }


def lire_etat(chemin):
    etat = lire_json(chemin)
    return etat if etat is not None else {}


def enregistrer_etat(chemin, empreintes):
    # Ces empreintes ne permettent pas de reconstruire les jetons ; le fichier
    # peut donc rester lisible pour le diagnostic sans elargir leur exposition.
    ecrire_json_atomique(chemin, {"empreintes": empreintes}, mode=0o644)


def appliquer_redemarrage(options, empreintes):
    if options.no_restart:
        logger.info("identifiants poses ; redemarrage differe a la demande de l'operateur")
        return 0
    succes, detail = redemarrer_runtime()
    if not succes:
        logger.error(detail)
        return 75
    try:
        enregistrer_etat(options.state_file, empreintes)
    except OSError as erreur:
        logger.error("enregistrement de l'etat impossible : %s", erreur)
        return 70
    logger.info(detail)
    return 0


def reconcilier(options):
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

    maintenant = time.time()
    marge = max(0.0, options.margin_days) * 24 * 3600
    chemins = {"media": options.media_file, "command": options.command_file}
    try:
        for chemin in chemins.values():
            securiser_permissions(chemin)
    except OSError as erreur:
        logger.error("securisation des identifiants impossible : %s", erreur)
        return 70
    courantes = empreintes_courantes(options)
    etat = lire_etat(options.state_file)
    appliquees = etat.get("empreintes") if isinstance(etat.get("empreintes"), dict) else None

    # La premiere execution etablit la reference de ce que le runtime a charge.
    # En cas d'echec de redemarrage ulterieur, elle reste volontairement sur
    # l'ancienne valeur : le passage suivant saura qu'il doit reessayer.
    if appliquees is None:
        appliquees = dict(courantes)
        try:
            enregistrer_etat(options.state_file, appliquees)
        except OSError as erreur:
            logger.error("initialisation de l'etat impossible : %s", erreur)
            return 70

    renouveler = [
        role for role, chemin in chemins.items()
        if doit_renouveler(chemin, marge, maintenant)
    ]
    if not renouveler:
        if courantes != appliquees:
            logger.info("identifiants modifies hors de cet outil : rechargement du runtime")
            return appliquer_redemarrage(options, courantes)
        logger.info("identifiants LiveKit valides au-dela de la marge de %.1f jours", options.margin_days)
        return 0

    logger.info("renouvellement requis pour : %s", ", ".join(sorted(renouveler)))
    try:
        reponse = recuperer(base, robot, cle)
    except (urllib.error.URLError, TimeoutError, ValueError) as erreur:
        # Une panne de console ne rend pas le robot fautif. Les identifiants en
        # place restent utilisables jusqu'a leur propre expiration et le timer
        # quotidien offrira une nouvelle occasion sans lever d'alerte.
        logger.info("console injoignable (%s) : identifiants en place conserves", erreur)
        return 0

    try:
        nouveaux = extraire_identifiants(reponse, maintenant)
    except ValueError as erreur:
        logger.error("reponse de la console refusee : %s", erreur)
        return 65

    modifies = []
    try:
        for role in ("media", "command"):
            actuel = lire_json(chemins[role])
            if actuel == nouveaux[role]:
                continue
            ecrire_json_atomique(chemins[role], nouveaux[role], mode=0o600)
            modifies.append(role)
    except OSError as erreur:
        logger.error("ecriture des identifiants impossible : %s", erreur)
        return 70

    apres = empreintes_courantes(options)
    if not modifies:
        logger.info("la console a renvoye les identifiants deja presents : aucun fichier modifie")
        if apres != appliquees:
            return appliquer_redemarrage(options, apres)
        return 0

    logger.info("identifiants renouveles : %s", ", ".join(modifies))
    return appliquer_redemarrage(options, apres)


def construire_arguments(argv=None):
    analyseur = argparse.ArgumentParser(description="Renouvelle les identifiants LiveKit du robot.")
    analyseur.add_argument("--config", type=Path, default=CONFIG_PAR_DEFAUT)
    analyseur.add_argument("--key-file", type=Path, default=CLE_PAR_DEFAUT)
    analyseur.add_argument("--media-file", type=Path, default=MEDIA_PAR_DEFAUT)
    analyseur.add_argument("--command-file", type=Path, default=COMMANDE_PAR_DEFAUT)
    analyseur.add_argument("--state-file", type=Path, default=ETAT_PAR_DEFAUT)
    analyseur.add_argument("--api-url", default="")
    analyseur.add_argument(
        "--margin-days", type=float,
        default=float(os.environ.get("OSCAR_CREDENTIALS_RENEWAL_DAYS", MARGE_JOURS_PAR_DEFAUT)),
    )
    analyseur.add_argument("--no-restart", action="store_true")
    analyseur.add_argument("--log-level", default="INFO")
    return analyseur.parse_args(argv)


def main(argv=None):
    options = construire_arguments(argv)
    logging.basicConfig(level=options.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return reconcilier(options)


if __name__ == "__main__":
    sys.exit(main())
