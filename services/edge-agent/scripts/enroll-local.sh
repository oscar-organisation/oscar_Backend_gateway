#!/usr/bin/env bash
# Enrolement d'un robot, execute sur le robot lui-meme.
#
# Le preambule colle par l'operateur a deja fait le strict minimum : poser la
# cle d'agent et extraire cette archive. A partir de la, le robot sait prouver
# qui il est, donc il peut aller chercher tout le reste lui-meme.
#
# Ce decoupage est volontaire. Le preambule tient dans un presse-papiers et ne
# fait rien d'autre que ce qui doit arriver avant que l'archive existe ; la
# logique, elle, vit ici, versionnee et relue comme le reste du paquet.
#
#   ./enroll-local.sh --robot oscar-04 --api https://.../api --profil rosmaster-m3pro
#
set -Eeuo pipefail

racine="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_dir="/etc/oscar"
cle_fichier="$config_dir/credentials/agent.key"

robot=""
api=""
profil=""
registre=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --robot) robot="$2"; shift 2 ;;
    --api) api="$2"; shift 2 ;;
    --profil) profil="$2"; shift 2 ;;
    --registre) registre="$2"; shift 2 ;;
    *) echo "Argument inconnu : $1" >&2; exit 64 ;;
  esac
done

for requis in robot api profil; do
  [[ -n "${!requis}" ]] || { echo "--$requis est obligatoire" >&2; exit 64; }
done

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "L'enrolement doit etre execute avec sudo." >&2
  exit 1
fi

etape() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

# --------------------------------------------------------------------------- #
#  1. La cle doit etre en place : c'est elle qui ouvre tout le reste
# --------------------------------------------------------------------------- #
[[ -s "$cle_fichier" ]] || {
  echo "Cle d'agent absente de $cle_fichier : le preambule n'a pas abouti." >&2
  exit 78
}
chmod 600 "$cle_fichier"

# Les appels passent par un fichier de configuration curl plutot que par -H :
# un en-tete donne en argument se lit dans `ps` par n'importe quel utilisateur
# de la machine pendant toute la duree de la requete.
travail="$(mktemp -d)"
trap 'rm -rf "$travail"' EXIT
printf 'header = "X-Oscar-Agent-Key: %s"\n' "$(cat "$cle_fichier")" > "$travail/curlrc"
chmod 600 "$travail/curlrc"

# --------------------------------------------------------------------------- #
#  2. Le profil materiel, compose avant l'installation
# --------------------------------------------------------------------------- #
# L'ordre compte : install.sh ne cree robot.env que s'il est absent. En
# l'ecrivant d'abord, on garde la main sur son contenu ; en le laissant faire,
# on heriterait du gabarit d'exemple et de ses CHANGE_ME.
etape "Profil materiel de la famille $profil"
profil_source="$racine/config/profiles/$profil.env"
[[ -r "$profil_source" ]] || {
  echo "Profil inconnu : $profil_source" >&2
  echo "Familles disponibles : $(ls -1 "$racine/config/profiles" | sed 's/\.env$//' | tr '\n' ' ')" >&2
  exit 78
}

install -d -m 0750 "$config_dir"
if [[ -f "$config_dir/robot.env" ]]; then
  echo "  robot.env existe deja : conserve tel quel."
else
  {
    cat "$profil_source"
    printf '\n# Renseigne a l enrolement, propre a ce robot.\n'
    printf 'OSCAR_ROBOT_ID=%s\n' "$robot"
    printf 'OSCAR_ROBOT_PROFILE=%s\n' "$profil"
    printf 'OSCAR_API_URL=%s\n' "$api"
    [[ -n "$registre" ]] && printf 'OSCAR_REGISTRY=%s\n' "$registre"
    printf 'OSCAR_MEDIA_TOKEN_FILE=%s/credentials/media.json\n' "$config_dir"
    printf 'OSCAR_COMMAND_TOKEN_FILE=%s/credentials/command.json\n' "$config_dir"
  } > "$config_dir/robot.env"
  chmod 0640 "$config_dir/robot.env"
  echo "  robot.env compose depuis $profil ($(grep -c '=' "$config_dir/robot.env") variables)."
fi

# --------------------------------------------------------------------------- #
#  3. Le paquet
# --------------------------------------------------------------------------- #
etape "Installation du paquet embarque"
"$racine/scripts/install.sh"

# --------------------------------------------------------------------------- #
#  4. Les identifiants temps reel, demandes par le robot lui-meme
# --------------------------------------------------------------------------- #
etape "Identifiants LiveKit"
curl -fsSL --config "$travail/curlrc" \
  "${api%/}/studio/runtime/robots/$robot/credentials" -o "$travail/credentials.json"

# La reponse est indexee par chemin de destination : on ecrit chaque valeur la
# ou le runtime l'attend, sans que ce script ait a connaitre l'arborescence.
python3 - "$travail/credentials.json" <<'PY'
import json
import os
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    reponse = json.load(source)

fichiers = reponse.get("fichiers") or {}
if not fichiers:
    raise SystemExit("reponse sans identifiants : enrolement interrompu")

for chemin, contenu in fichiers.items():
    os.makedirs(os.path.dirname(chemin), mode=0o700, exist_ok=True)
    # Ecriture puis renommage : un fichier de jeton a moitie ecrit empecherait
    # le runtime de demarrer, et le diagnostic porterait a faux.
    temporaire = chemin + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as sortie:
        json.dump(contenu, sortie, ensure_ascii=False, indent=2)
    os.chmod(temporaire, 0o600)
    os.replace(temporaire, chemin)
    print("  %s" % chemin)
PY

# --------------------------------------------------------------------------- #
#  5. Mise en service
# --------------------------------------------------------------------------- #
etape "Mise en service"
/usr/local/bin/oscarctl activate

etape "Enrolement termine"
cat <<FIN

  Robot      : $robot
  Famille    : $profil
  Console    : $api

  Le robot interroge desormais la console toutes les 45 secondes. Sa fiche
  doit passer de « jamais vu » a « vu a l'instant » dans ce delai.

  Diagnostic : oscarctl doctor
FIN
