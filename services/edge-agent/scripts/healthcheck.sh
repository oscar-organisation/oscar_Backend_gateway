#!/usr/bin/env bash
set -Eeuo pipefail

quiet=false
[[ "${1:-}" == "--quiet" ]] && quiet=true
container="${OSCAR_CONTAINER_NAME:-oscar-edge}"
status=0

emit() {
  if [[ "$quiet" == false || "$1" != "OK" ]]; then
    printf '[%s] %s\n' "$1" "$2"
  fi
}

if ! docker inspect "$container" >/dev/null 2>&1; then
  emit ERREUR "conteneur $container absent"
  exit 1
fi

running="$(docker inspect -f '{{.State.Running}}' "$container")"
health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container")"
[[ "$running" == true ]] || { emit ERREUR "conteneur arrete"; status=1; }
[[ "$health" == healthy ]] || { emit ERREUR "sante conteneur: $health"; status=1; }

for pattern in oscar_robot_media.py command_agent.py; do
  if docker exec "$container" pgrep -f "[$(printf '%s' "$pattern" | cut -c1)]${pattern:1}" >/dev/null 2>&1; then
    emit OK "$pattern actif"
  else
    emit ERREUR "$pattern absent"
    status=1
  fi
done

if docker exec "$container" bash -lc \
  'source "${OSCAR_ROS_SETUP:-/opt/ros/${ROS_DISTRO:-humble}/setup.bash}" >/dev/null 2>&1; ros2 topic info "${OSCAR_CAMERA_TOPIC:-/camera/color/image_raw}"' \
  >/dev/null 2>&1; then
  emit OK "topic camera visible"
else
  emit ERREUR "topic camera invisible"
  status=1
fi

if docker exec "$container" bash -lc \
  'source "${OSCAR_ROS_SETUP:-/opt/ros/${ROS_DISTRO:-humble}/setup.bash}" >/dev/null 2>&1; ros2 topic info "${OSCAR_CMD_VEL_TOPIC:-/cmd_vel}"' \
  >/dev/null 2>&1; then
  emit OK "topic cmd_vel visible"
else
  emit ERREUR "topic cmd_vel invisible"
  status=1
fi

exit "$status"
