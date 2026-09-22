#!/usr/bin/env bash
set -Eeuo pipefail

edge_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(tr -d '[:space:]' < "$edge_dir/VERSION")"
dist_dir="$edge_dir/dist"
stage_dir="$dist_dir/oscar-edge-$version"
archive="$dist_dir/oscar-edge-$version.tar.gz"

runtime_files=(
  command_agent.py
  livekit_publisher.py
  oscar_robot_media.py
  robot_control.py
  ros2_image_source.py
  teleop_mapping.py
)

rm -rf "$stage_dir"
mkdir -p "$stage_dir/runtime" "$dist_dir"

for path in README.md VERSION IMAGE manifest.json compose.yaml compose.build.yaml config contracts docker docs scripts systemd tools; do
  cp -a "$edge_dir/$path" "$stage_dir/$path"
done

for file in "${runtime_files[@]}"; do
  if [[ ! -f "$edge_dir/runtime/$file" ]]; then
    echo "Module runtime absent: runtime/$file" >&2
    exit 1
  fi
  cp "$edge_dir/runtime/$file" "$stage_dir/runtime/$file"
done

find "$stage_dir" -type f -name '*.sh' -exec chmod 0755 {} +
tar -C "$dist_dir" -czf "$archive" "oscar-edge-$version"
printf 'Release construite: %s\n' "$archive"
