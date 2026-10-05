#!/usr/bin/env bash
# Raccorde un robot au registre d'images OSCAR.
#
# A passer une fois par robot, a la mise en service. Deux choses seulement :
# l'autorite qui signe le certificat du registre, pour que Docker le verifie
# au lieu de l'accepter aveuglement, et un compte en lecture seule. Un robot
# ne pousse jamais d'image ; le registre refuse d'ailleurs l'ecriture a ce
# compte, de sorte qu'une cle qui fuite ne contamine pas la flotte.
#
#   sudo ./provision-registry.sh ca.crt oscar-robot          registre a autorite privee
#   sudo ./provision-registry.sh - 'compte-machine-oscar+...'  Harbor, certificat public
#
# Le mot de passe est demande sur l'entree standard, jamais passe en argument :
# la ligne de commande est visible de tout le systeme.
set -Eeuo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "A executer avec sudo." >&2
  exit 1
fi

autorite="${1:-}"
compte="${2:-oscar-robot}"
config="${OSCAR_CONFIG_FILE:-/etc/oscar/robot.env}"

# L'autorite n'est utile qu'au registre a certificat prive. Harbor presente un
# certificat Let's Encrypt, que Docker verifie deja : on passe alors "-".
if [[ -z "$autorite" || ( "$autorite" != "-" && ! -r "$autorite" ) ]]; then
  echo "Usage: provision-registry.sh CHEMIN_CA|- [COMPTE]" >&2
  exit 2
fi

registry="$(sed -n 's/^OSCAR_REGISTRY=//p' "$config" | tail -1 | tr -d '"'"'"'\r' | tr -d '[:space:]')"
if [[ -z "$registry" ]]; then
  echo "OSCAR_REGISTRY absent de $config." >&2
  exit 1
fi

famille="$(sed -n 's/^OSCAR_ROBOT_PROFILE=//p' "$config" | tail -1 | tr -d '"'"'"'\r' | tr -d '[:space:]')"
if [[ -z "$famille" ]]; then
  echo "OSCAR_ROBOT_PROFILE absent de $config." >&2
  exit 1
fi

if [[ "$autorite" != "-" ]]; then
  # Docker cherche l'autorite a un emplacement nomme d'apres le registre.
  cible="/etc/docker/certs.d/$registry"
  install -d -m 0755 "$cible"
  install -m 0644 "$autorite" "$cible/ca.crt"
  echo "Autorite installee: $cible/ca.crt"
fi

printf 'Mot de passe du compte %s: ' "$compte" >&2
read -r -s motdepasse
printf '\n' >&2

# HOME est force a /root, et ce n'est pas un detail : sudo conserve le HOME
# de l'appelant sur cet hote, si bien que les identifiants atterrissaient dans
# /home/jetson/.docker/. Les minuteries systemd, elles, tournent avec
# HOME=/root : le tirage automatique echouait alors en "unauthorized" sans
# qu'aucun test manuel ne le montre.
install -d -m 0700 /root/.docker
if ! printf '%s' "$motdepasse" \
  | HOME=/root docker login "$registry" --username "$compte" --password-stdin; then
  echo "Connexion au registre refusee." >&2
  exit 1
fi
unset motdepasse
chmod 0600 /root/.docker/config.json

# Verification dans les conditions d'une minuterie : environnement vide, root.
# La sonde vise le depot de la famille avec une etiquette qui n'existe pas :
# une reponse "introuvable" prouve que le compte lit ce depot, un refus
# prouverait le contraire. registry:2 dit "manifest unknown", Harbor
# "artifact ... not found".
if ! env -i PATH=/usr/bin:/bin HOME=/root docker pull "$registry/oscar/edge-$famille:sonde-inexistante" 2>&1 \
  | grep -Eq "manifest unknown|artifact .* not found"; then
  echo "Les identifiants ne sont pas lisibles dans les conditions de systemd." >&2
  exit 1
fi

echo "Robot raccorde au registre $registry en lecture."
