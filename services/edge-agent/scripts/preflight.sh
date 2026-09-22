#!/usr/bin/env bash
set -Eeuo pipefail

config="${OSCAR_CONFIG_FILE:-/etc/oscar/robot.env}"
root="${OSCAR_HOME:-/opt/oscar/current}"
errors=0

ok() { printf '[OK] %s\n' "$*"; }
fail() { printf '[ERREUR] %s\n' "$*" >&2; errors=$((errors + 1)); }

[[ -r "$config" ]] && ok "configuration lisible" || fail "configuration absente: $config"
[[ -r "$root/manifest.json" ]] && ok "release OSCAR presente" || fail "release absente: $root"
command -v docker >/dev/null && ok "Docker present" || fail "Docker absent"
docker compose version >/dev/null 2>&1 && ok "Docker Compose v2 present" || fail "Docker Compose v2 absent"

if [[ -r "$config" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$config"
  set +a
  [[ -n "${OSCAR_ROBOT_ID:-}" ]] && ok "robot: $OSCAR_ROBOT_ID" || fail "OSCAR_ROBOT_ID absent"
  [[ -n "${OSCAR_REGISTRY:-}" ]] \
    && ok "registre d'images: $OSCAR_REGISTRY" || fail "OSCAR_REGISTRY non configure"
fi

# L'image que la release attend doit etre sur le disque avant que compose ne
# tente de la demarrer. Le prevol garde ce role de derniere barriere : il
# tourne aussi apres un retour arriere, ou l'image attendue change.
release_env="${OSCAR_RELEASE_FILE:-/etc/oscar/release.env}"
if [[ -r "$release_env" ]]; then
  image="$(sed -n 's/^OSCAR_EDGE_IMAGE=//p' "$release_env" | tail -1)"
  if [[ -z "$image" ]]; then
    fail "OSCAR_EDGE_IMAGE absent de $release_env"
  elif docker image inspect "$image" >/dev/null 2>&1; then
    ok "image du runtime presente: $image"
  else
    fail "image du runtime absente: $image (oscarctl pull)"
  fi
else
  fail "reference d'image absente: $release_env (reinstaller le paquet)"
fi

# Reconciliation des bundles : optionnelle, mais si elle est configuree a
# moitie, autant le dire maintenant plutot qu'au premier deploiement refuse.
if [[ -n "${OSCAR_API_URL:-}" ]]; then
  agent_key="/etc/oscar/credentials/agent.key"
  if [[ -r "$agent_key" && -s "$agent_key" ]]; then
    perms="$(stat -c '%a' "$agent_key" 2>/dev/null || stat -f '%Lp' "$agent_key")"
    if [[ "$perms" == 600 || "$perms" == 400 ]]; then
      ok "cle d'agent presente et protegee"
    else
      fail "cle d'agent lisible par d'autres comptes ($perms): chmod 600 $agent_key"
    fi
  else
    fail "OSCAR_API_URL configure mais cle d'agent absente: $agent_key"
  fi
fi

python3 "$root/tools/validate_config.py" \
  --env "$config" \
  --media-token /etc/oscar/credentials/media.json \
  --command-token /etc/oscar/credentials/command.json || errors=$((errors + 1))

if [[ "$errors" -gt 0 ]]; then
  printf 'Prevol refuse: %d erreur(s). Aucun service ne sera lance.\n' "$errors" >&2
  exit 1
fi
ok "prevol valide"
