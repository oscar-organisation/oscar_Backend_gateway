#!/usr/bin/env bash
# Verifie la signature d'une image avant qu'elle ne tourne sur le robot.
#
#   verify-image.sh REFERENCE@sha256:... CLE_PUBLIQUE
#
# La CI signe chaque image avec la cle privee de l'organisation ; le robot
# n'a que la cle publique, livree dans la release. Un compte du registre
# compromis ne suffit donc pas a faire tourner du code sur la flotte : il
# faudrait aussi la cle de signature, qui ne quitte jamais la CI.
#
# Cosign tourne dans un conteneur, a une version figee : rien a installer sur
# l'hote. Il lit les identifiants du registre de root, en lecture seule.
set -Eeuo pipefail

reference="${1:?reference d image attendue}"
cle="${2:?cle publique attendue}"
cosign="${OSCAR_COSIGN_IMAGE:-ghcr.io/sigstore/cosign/cosign:v2.4.1}"

[[ "$reference" == *@sha256:* ]] || {
  echo "Signature verifiable sur une empreinte seulement, pas sur : $reference" >&2
  exit 65
}
[[ -r "$cle" ]] || { echo "Cle publique illisible : $cle" >&2; exit 78; }

# Le journal public de transparence n'est pas utilise : les images sont
# privees, et la confiance repose sur la cle de l'organisation.
exec docker run --rm --network host --user 0 \
  -e DOCKER_CONFIG=/registre \
  -v /root/.docker:/registre:ro \
  -v "$(readlink -f "$cle"):/cosign.pub:ro" \
  "$cosign" verify --key /cosign.pub --insecure-ignore-tlog=true "$reference" >/dev/null
