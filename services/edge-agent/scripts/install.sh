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
switch=true

# --no-switch depose la release sur le disque sans la mettre en service.
#
# La distinction est necessaire : la mise a jour automatique doit pouvoir
# tirer l'image de la nouvelle version *avant* de basculer dessus. Tant que
# l'installation deplacait elle-meme /opt/oscar/current, ce controle arrivait
# trop tard — le lien avait deja bouge quand le tirage echouait, et le robot
# se retrouvait avec un lien, une reference d'image et un conteneur qui
# racontaient trois versions differentes.
for argument in "$@"; do
  case "$argument" in
    --activate) activate=true ;;
    --no-switch) switch=false ;;
  esac
done

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
else
  # Un robot deja en service gardait son profil tel quel, donc une variable
  # apparue dans une version ulterieure ne l'atteignait jamais. La reprise
  # automatique du port USB est restee inerte pour cette raison : son code
  # etait installe, la variable qui la declenche absente.
  #
  # On ajoute ce qui manque, avec la valeur par defaut du modele, et on ne
  # touche a rien de ce qui existe : ce fichier porte les reglages propres au
  # chassis, et l'ecraser effacerait le travail de mise en service.
  ajoutees=0
  while IFS= read -r ligne; do
    [[ "$ligne" =~ ^[A-Z_]+= ]] || continue
    cle="${ligne%%=*}"
    grep -qE "^[[:space:]]*#?[[:space:]]*${cle}=" "$config_dir/robot.env" && continue
    if (( ajoutees == 0 )); then
      printf '\n# Ajoute par la mise a jour du paquet %s.\n' "$version" >> "$config_dir/robot.env"
    fi
    printf '%s\n' "$ligne" >> "$config_dir/robot.env"
    ajoutees=$((ajoutees + 1))
  done < "$bundle_dir/config/robot.env.example"
  if (( ajoutees > 0 )); then
    echo "$ajoutees variable(s) ajoutee(s) a $config_dir/robot.env"
  fi
fi

# Configuration issue du bundle : vide tant que rien n'a ete publie, mais
# presente, car compose refuse de demarrer sur un env_file manquant.
if [[ ! -f "$config_dir/bundle.env" ]]; then
  printf '# Rempli par oscar-bundle-sync des la premiere reconciliation.\n' \
    > "$config_dir/bundle.env"
  chmod 0640 "$config_dir/bundle.env"
fi

if [[ "$switch" == true ]]; then
  # Identite de l'image, posee par le paquet a chaque installation.
  #
  # Cette valeur vivait dans robot.env, ou l'operateur la maintenait a la main.
  # Elle y restait figee quand une nouvelle version arrivait, et le robot
  # relancait alors l'ancienne image avec les nouveaux outils d'hote : les
  # modules du runtime ne changeaient jamais. Le paquet connait sa propre
  # version ; c'est donc lui qui l'ecrit.
  install -m 0755 "$bundle_dir/scripts/write-release-env.sh" /usr/local/libexec/oscar-release-env
  /usr/local/libexec/oscar-release-env "$release_dir"

  ln -sfn "$release_dir" /opt/oscar/current
  install -m 0755 "$bundle_dir/scripts/oscarctl" /usr/local/bin/oscarctl
  install -m 0755 "$bundle_dir/scripts/preflight.sh" /usr/local/libexec/oscar-preflight
  install -m 0755 "$bundle_dir/scripts/healthcheck.sh" /usr/local/bin/oscar-healthcheck
  install -m 0755 "$bundle_dir/scripts/network-recovery.sh" /usr/local/libexec/oscar-network-recovery
  install -m 0755 "$bundle_dir/tools/bundle_sync.py" /usr/local/libexec/oscar-bundle-sync
  install -m 0755 "$bundle_dir/tools/release_sync.py" /usr/local/libexec/oscar-release-sync
  install -m 0755 "$bundle_dir/tools/credentials_sync.py" /usr/local/libexec/oscar-credentials-sync
  install -m 0644 "$bundle_dir/systemd/oscar-chassis.service" /etc/systemd/system/oscar-chassis.service
  install -m 0644 "$bundle_dir/systemd/oscar-edge.service" /etc/systemd/system/oscar-edge.service
  install -m 0644 "$bundle_dir/systemd/oscar-edge-bridge.service" /etc/systemd/system/oscar-edge-bridge.service
  install -m 0644 "$bundle_dir/systemd/oscar-edge-health.service" /etc/systemd/system/oscar-edge-health.service
  install -m 0644 "$bundle_dir/systemd/oscar-edge-health.timer" /etc/systemd/system/oscar-edge-health.timer
  install -m 0644 "$bundle_dir/systemd/oscar-edge-network.service" /etc/systemd/system/oscar-edge-network.service
  install -m 0644 "$bundle_dir/systemd/oscar-edge-network.timer" /etc/systemd/system/oscar-edge-network.timer
  install -m 0644 "$bundle_dir/systemd/oscar-edge-sync.service" /etc/systemd/system/oscar-edge-sync.service
  install -m 0644 "$bundle_dir/systemd/oscar-edge-sync.timer" /etc/systemd/system/oscar-edge-sync.timer
  install -m 0644 "$bundle_dir/systemd/oscar-edge-release.service" /etc/systemd/system/oscar-edge-release.service
  install -m 0644 "$bundle_dir/systemd/oscar-edge-release.timer" /etc/systemd/system/oscar-edge-release.timer
  install -m 0644 "$bundle_dir/systemd/oscar-edge-credentials.service" /etc/systemd/system/oscar-edge-credentials.service
  install -m 0644 "$bundle_dir/systemd/oscar-edge-credentials.timer" /etc/systemd/system/oscar-edge-credentials.timer
  systemctl daemon-reload
  # Les pilotes vivent dans leur propre unite depuis 0.6.0. Elle est activee
  # ici et non dans `oscarctl activate`, qu'une mise a jour ne rejoue pas ;
  # oscar-edge.service la demarre lui-meme a sa prochaine relance.
  systemctl enable oscar-chassis.service
  # Une mise a jour automatisee ne repasse pas par `oscarctl activate`. Sur un
  # robot deja enrole, le nouveau timer doit donc entrer en service des que la
  # release qui le contient est installee.
  if grep -qs '^OSCAR_API_URL=.\+' "$config_dir/robot.env"; then
    systemctl enable --now oscar-edge-credentials.timer
  fi
fi

if [[ "$switch" != true ]]; then
  echo "OSCAR Edge $version depose dans $release_dir (pas encore en service)."
  exit 0
fi

echo "OSCAR Edge $version installe dans $release_dir"
echo "Renseigner /etc/oscar/robot.env et /etc/oscar/credentials/*.json."
echo "Pour recevoir les bundles publies: OSCAR_API_URL dans robot.env et la cle"
echo "d'agent dans /etc/oscar/credentials/agent.key (chmod 600)."

if [[ "$activate" == true ]]; then
  /usr/local/bin/oscarctl activate
fi
