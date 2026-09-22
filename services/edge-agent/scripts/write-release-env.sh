#!/usr/bin/env bash
# Ecrit /etc/oscar/release.env : la reference de l'image que la release en
# service attend.
#
# Deux chemins y menent et doivent donner le meme resultat : l'installation
# d'un paquet, et `oscarctl activate` apres que l'operateur a renseigne le
# registre dans robot.env. D'ou cet outil unique plutot que deux copies de la
# meme regle.
set -Eeuo pipefail

release_dir="${1:-/opt/oscar/current}"
config="${OSCAR_CONFIG_FILE:-/etc/oscar/robot.env}"
sortie="${OSCAR_RELEASE_FILE:-/etc/oscar/release.env}"

version="$(tr -d '[:space:]' < "$release_dir/VERSION")"
registry="$(sed -n 's/^OSCAR_REGISTRY=//p' "$config" | tail -1 | tr -d '"'"'"'\r' | tr -d '[:space:]')"
if [[ -z "$registry" ]]; then
  echo "OSCAR_REGISTRY absent de $config : registre d'images inconnu." >&2
  exit 1
fi
famille="$(sed -n 's/^OSCAR_ROBOT_PROFILE=//p' "$config" | tail -1 | tr -d '"'"'"'\r' | tr -d '[:space:]')"
if [[ -z "$famille" ]]; then
  echo "OSCAR_ROBOT_PROFILE absent de $config : famille de chassis inconnue." >&2
  exit 1
fi
depot="$(tr -d '[:space:]' < "$release_dir/IMAGE" 2>/dev/null || true)"
depot="${depot:-oscar/edge}"

# Une version du paquet donne une image par famille de chassis, pas une seule :
# chacune porte la base ROS de son constructeur. Le profil entre donc dans le
# nom, faute de quoi deux chassis se disputeraient le meme tag.

cat > "$sortie" <<RELEASE
# Ecrit par le paquet OSCAR Edge. Ne pas editer : toute modification est
# perdue a la prochaine installation ou bascule de version.
OSCAR_EDGE_VERSION=$version
OSCAR_EDGE_IMAGE=$registry/$depot-$famille:$version
RELEASE
chmod 0644 "$sortie"
