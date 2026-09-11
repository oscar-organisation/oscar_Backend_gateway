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
  [[ -n "${ROBOT_BASE_IMAGE:-}" && "${ROBOT_BASE_IMAGE:-}" != CHANGE_ME* ]] \
    && ok "image ROS constructeur configuree" || fail "ROBOT_BASE_IMAGE non configuree"
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
