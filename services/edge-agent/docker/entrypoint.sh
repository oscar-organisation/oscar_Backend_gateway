#!/usr/bin/env bash
set -Eeuo pipefail

source_if_present() {
  local file="$1"
  if [[ -n "$file" && -f "$file" ]]; then
    set +u
    # shellcheck disable=SC1090
    source "$file"
    set -u
  fi
}

source_if_present "${OSCAR_ROS_SETUP:-/opt/ros/${ROS_DISTRO:-humble}/setup.bash}"
source_if_present "${OSCAR_VENDOR_SETUP:-}"

required=(OSCAR_ROBOT_ID OSCAR_MEDIA_TOKEN_FILE OSCAR_COMMAND_TOKEN_FILE)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "[oscar-edge] variable obligatoire absente: $name" >&2
    exit 78
  fi
done

for token_file in "$OSCAR_MEDIA_TOKEN_FILE" "$OSCAR_COMMAND_TOKEN_FILE"; do
  if [[ ! -r "$token_file" ]]; then
    echo "[oscar-edge] credential illisible: $token_file" >&2
    exit 78
  fi
done

cleanup() {
  trap - TERM INT EXIT
  kill -TERM "${media_pid:-}" "${command_pid:-}" 2>/dev/null || true
  wait "${media_pid:-}" "${command_pid:-}" 2>/dev/null || true
}
trap cleanup TERM INT EXIT

python3 /opt/oscar/runtime/oscar_robot_media.py \
  --token-file "$OSCAR_MEDIA_TOKEN_FILE" \
  --topic "${OSCAR_CAMERA_TOPIC:-/camera/color/image_raw}" \
  --track-name "${OSCAR_VIDEO_TRACK:-camera-front}" \
  --width "${OSCAR_CAMERA_WIDTH:-640}" \
  --height "${OSCAR_CAMERA_HEIGHT:-480}" \
  --fps "${OSCAR_CAMERA_FPS:-30}" \
  --max-bitrate "${OSCAR_CAMERA_MAX_BITRATE:-1500000}" \
  --log-level "${LOG_LEVEL:-INFO}" &
media_pid=$!

command_args=(
  --apply ros2
  --token-file "$OSCAR_COMMAND_TOKEN_FILE"
  --topic "${OSCAR_INPUT_TOPIC:-oscar.xr.input}"
  --command-topic "${OSCAR_COMMAND_ECHO_TOPIC:-oscar.robot.command}"
  --cmd-vel-topic "${OSCAR_CMD_VEL_TOPIC:-/cmd_vel}"
  --watchdog-ms "${OSCAR_WATCHDOG_MS:-300}"
  --control-hz "${OSCAR_CONTROL_HZ:-30}"
  --max-vx "${OSCAR_MAX_VX_MPS:-0.40}"
  --max-vy "${OSCAR_MAX_VY_MPS:-0.20}"
  --max-wz "${OSCAR_MAX_WZ_RADPS:-0.80}"
  --log-level "${LOG_LEVEL:-INFO}"
)
if [[ "${OSCAR_INVERT_LATERAL:-false}" == "true" ]]; then
  command_args+=(--invert-lateral)
fi
python3 /opt/oscar/runtime/command_agent.py "${command_args[@]}" &
command_pid=$!

echo "[oscar-edge] runtime ${OSCAR_EDGE_VERSION:-dev} actif pour ${OSCAR_ROBOT_ID}"
set +e
wait -n "$media_pid" "$command_pid"
exit_code=$?
set -e
echo "[oscar-edge] un agent s'est arrete (code=$exit_code), redemarrage supervise demande" >&2
exit "$exit_code"
