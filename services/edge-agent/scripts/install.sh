#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "L'installation doit etre executee avec sudo." >&2
  exit 1
fi

bundle_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(tr -d '[:space:]' < "$bundle_dir/VERSION")"
release_dir="/opt/oscar/releases/$version"
config_dir="/etc/oscar"
activate=false

if [[ "${1:-}" == "--activate" ]]; then
  activate=true
fi

for command in docker systemctl install cp ln; do
  command -v "$command" >/dev/null || {
    echo "Dependance absente: $command" >&2
    exit 1
  }
done
docker compose version >/dev/null 2>&1 || {
  echo "Docker Compose v2 est requis (commande: docker compose)." >&2
  exit 1
}

if [[ ! -d "$bundle_dir/runtime" ]]; then
  echo "Bundle incomplet: runtime/ absent. Utiliser build-release.sh." >&2
  exit 1
fi

install -d -m 0755 /opt/oscar/releases /var/lib/oscar /var/log/oscar
install -d -m 0750 "$config_dir"
install -d -m 0700 "$config_dir/credentials"
if [[ -e "$release_dir" ]]; then
  echo "Release $version deja installee; son contenu immuable est conserve."
else
  install -d -m 0755 "$release_dir"
  cp -a "$bundle_dir/." "$release_dir/"
fi

if [[ ! -f "$config_dir/robot.env" ]]; then
  install -m 0640 "$bundle_dir/config/robot.env.example" "$config_dir/robot.env"
  echo "Configuration initiale creee: $config_dir/robot.env"
fi

ln -sfn "$release_dir" /opt/oscar/current
install -m 0755 "$bundle_dir/scripts/oscarctl" /usr/local/bin/oscarctl
install -m 0755 "$bundle_dir/scripts/preflight.sh" /usr/local/libexec/oscar-preflight
install -m 0755 "$bundle_dir/scripts/healthcheck.sh" /usr/local/bin/oscar-healthcheck
install -m 0755 "$bundle_dir/scripts/network-recovery.sh" /usr/local/libexec/oscar-network-recovery
install -m 0644 "$bundle_dir/systemd/oscar-edge.service" /etc/systemd/system/oscar-edge.service
install -m 0644 "$bundle_dir/systemd/oscar-edge-health.service" /etc/systemd/system/oscar-edge-health.service
install -m 0644 "$bundle_dir/systemd/oscar-edge-health.timer" /etc/systemd/system/oscar-edge-health.timer
install -m 0644 "$bundle_dir/systemd/oscar-edge-network.service" /etc/systemd/system/oscar-edge-network.service
install -m 0644 "$bundle_dir/systemd/oscar-edge-network.timer" /etc/systemd/system/oscar-edge-network.timer
systemctl daemon-reload

echo "OSCAR Edge $version installe dans $release_dir"
echo "Renseigner /etc/oscar/robot.env et /etc/oscar/credentials/*.json."

if [[ "$activate" == true ]]; then
  /usr/local/bin/oscarctl activate
fi
