#!/usr/bin/env bash
set -Eeuo pipefail

container="${OSCAR_NETWORK_CONTAINER:-oscar-edge}"
exit_node="${OSCAR_TAILSCALE_EXIT_NODE:-}"
state_file="${OSCAR_NETWORK_STATE_FILE:-/run/oscar/network.state}"
livekit_host="${OSCAR_LIVEKIT_HOST:-stream-livekit.oscar-bot.com}"

log() { logger -t oscar-network "$*"; printf '%s\n' "$*"; }

install -d -m 0755 "$(dirname "$state_file")"
exec 9>"${state_file}.lock"
flock -n 9 || exit 0

if [[ -n "$exit_node" ]] && command -v tailscale >/dev/null 2>&1; then
  if tailscale debug prefs 2>/dev/null | grep -q '"ExitNodeID": ""'; then
    tailscale set --exit-node="$exit_node" --exit-node-allow-lan-access=true
    log "noeud de sortie Tailscale active: $exit_node"
  fi
fi

route_line="$(ip -4 route show default 2>/dev/null | awk '$0 !~ / dev tailscale0( |$)/ { print; exit }')"
[[ -n "$route_line" ]] || exit 0
default_iface="$(awk '{ for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit } }' <<<"$route_line")"
default_gateway="$(awk '{ for (i = 1; i <= NF; i++) if ($i == "via") { print $(i + 1); exit } }' <<<"$route_line")"
[[ -n "$default_iface" ]] || exit 0
physical_addr="$(ip -o -4 addr show dev "$default_iface" scope global 2>/dev/null | awk 'NR == 1 { print $4 }')"

# Deliberately omit route metrics and virtual-interface addresses. Tailscale can
# rewrite those while the physical network is unchanged, which must not restart
# the realtime agents.
fingerprint="$default_iface|$default_gateway|$physical_addr"

if [[ ! -s "$state_file" ]]; then
  printf '%s\n' "$fingerprint" >"$state_file"
  exit 0
fi
[[ "$(cat "$state_file")" == "$fingerprint" ]] && exit 0
printf '%s\n' "$fingerprint" >"$state_file"

for _ in {1..6}; do
  getent ahostsv4 "$livekit_host" >/dev/null 2>&1 && break
  sleep 5
done
getent ahostsv4 "$livekit_host" >/dev/null 2>&1 || {
  log "reseau change, DNS LiveKit indisponible; nouvelle tentative au prochain passage"
  rm -f "$state_file"
  exit 0
}

docker inspect "$container" >/dev/null 2>&1 || exit 0
old_pids="$(docker exec "$container" sh -c "pgrep -f '^python3 .*oscar_robot_media.py|^python3 .*command_agent.py' || true")"
[[ -n "$old_pids" ]] || exit 0
log "reseau change; reconnexion des agents LiveKit dans $container"
docker exec "$container" kill -TERM $old_pids 2>/dev/null || true
sleep 10
for pid in $old_pids; do
  if docker exec "$container" kill -0 "$pid" 2>/dev/null; then
    docker exec "$container" kill -KILL "$pid" 2>/dev/null || true
  fi
done
