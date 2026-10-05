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
  arret_securite.py
)

rm -rf "$stage_dir"
mkdir -p "$stage_dir/runtime" "$dist_dir"

for path in README.md VERSION IMAGE manifest.json compose.yaml config contracts docker docs scripts systemd tools; do
  cp -a "$edge_dir/$path" "$stage_dir/$path"
done

for file in "${runtime_files[@]}"; do
  if [[ ! -f "$edge_dir/runtime/$file" ]]; then
    echo "Module runtime absent: runtime/$file" >&2
    exit 1
  fi
  cp "$edge_dir/runtime/$file" "$stage_dir/runtime/$file"
done

# L'empreinte de l'image, fournie par la CI qui vient de la construire et de
# la signer. Sans elle, la release designerait une etiquette, que n'importe
# quel compte d'ecriture du registre pourrait reecrire.
if [[ -n "${OSCAR_EDGE_DIGEST:-}" ]]; then
  [[ "$OSCAR_EDGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || {
    echo "Empreinte invalide: $OSCAR_EDGE_DIGEST" >&2
    exit 1
  }
  printf '%s\n' "$OSCAR_EDGE_DIGEST" > "$stage_dir/IMAGE_DIGEST"
elif [[ "${OSCAR_RELEASE_SANS_EMPREINTE:-}" != 1 ]]; then
  echo "OSCAR_EDGE_DIGEST absent : une release designe son image par empreinte." >&2
  exit 1
fi

find "$stage_dir" -type f -name '*.sh' -exec chmod 0755 {} +
# COPYFILE_DISABLE : sur macOS, tar glissait un fichier « ._* » de metadonnees
# a cote de chaque fichier de l'archive.
COPYFILE_DISABLE=1 tar --no-xattrs -C "$dist_dir" -czf "$archive" "oscar-edge-$version"
printf 'Release construite: %s\n' "$archive"
