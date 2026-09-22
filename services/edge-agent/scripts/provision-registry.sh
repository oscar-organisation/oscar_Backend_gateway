#!/usr/bin/env bash
# Raccorde un robot au registre d'images OSCAR.
#
# A passer une fois par robot, a la mise en service. Deux choses seulement :
# l'autorite qui signe le certificat du registre, pour que Docker le verifie
# au lieu de l'accepter aveuglement, et un compte en lecture seule. Un robot
# ne pousse jamais d'image ; le registre refuse d'ailleurs l'ecriture a ce
# compte, de sorte qu'une cle qui fuite ne contamine pas la flotte.
#
#   sudo ./provision-registry.sh ca.crt oscar-robot
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

if [[ -z "$autorite" || ! -r "$autorite" ]]; then
  echo "Usage: provision-registry.sh CHEMIN_CA [COMPTE]" >&2
  exit 2
fi

registry="$(sed -n 's/^OSCAR_REGISTRY=//p' "$config" | tail -1 | tr -d '"'"'"'\r' | tr -d '[:space:]')"
if [[ -z "$registry" ]]; then
  echo "OSCAR_REGISTRY absent de $config." >&2
  exit 1
fi

# Docker cherche l'autorite a un emplacement nomme d'apres le registre.
cible="/etc/docker/certs.d/$registry"
install -d -m 0755 "$cible"
install -m 0644 "$autorite" "$cible/ca.crt"
echo "Autorite installee: $cible/ca.crt"

printf 'Mot de passe du compte %s: ' "$compte" >&2
read -r -s motdepasse
printf '\n' >&2

if ! printf '%s' "$motdepasse" | docker login "$registry" --username "$compte" --password-stdin; then
  echo "Connexion au registre refusee." >&2
  exit 1
fi
unset motdepasse

echo "Robot raccorde au registre $registry en lecture."
