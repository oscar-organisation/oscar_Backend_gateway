#!/usr/bin/env bash
# Conteneur « chassis » : les pilotes du constructeur et l'arret de securite.
#
# Il tourne avec l'image du constructeur, deja sur le robot, que ce paquet ne
# modifie pas : ce script et l'arret de securite y sont montes en lecture
# seule depuis la release en service. Le runtime OSCAR vit dans un autre
# conteneur ; une mise a jour d'OSCAR ne redemarre donc plus les pilotes.
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

pids=()

# Mise en route declaree par le profil materiel et choisie par le bundle. Sur
# un robot sorti de carton, personne n'a lance les pilotes : le deploiement
# doit le faire, sinon les agents s'abonnent a des topics que rien ne publie.
demarrer_bringup() {
  local total="${OSCAR_BRINGUP_COUNT:-0}"
  [[ "$total" =~ ^[0-9]+$ ]] || return 0
  local index variable commande attente_variable attente
  for ((index = 1; index <= total; index++)); do
    variable="OSCAR_BRINGUP_${index}"
    commande="${!variable:-}"
    [[ -z "$commande" ]] && continue
    echo "[oscar-chassis] mise en route ${index}/${total} : ${commande}"
    bash -c "exec ${commande}" &
    pids+=($!)
    attente_variable="OSCAR_BRINGUP_${index}_DELAY"
    attente="${!attente_variable:-0}"
    [[ "$attente" =~ ^[0-9]+$ ]] && (( attente > 0 )) && sleep "$attente"
  done
}

cleanup() {
  trap - TERM INT EXIT
  (( ${#pids[@]} )) || return 0
  kill -TERM "${pids[@]}" 2>/dev/null || true
  # Un ros2 launch eteint ses noeuds un par un et peut y passer plusieurs
  # dizaines de secondes : l'attente est bornee pour que le conteneur ne
  # survive pas a son propre arret.
  local limite="${OSCAR_STOP_TIMEOUT:-20}" restants pid
  for (( attente = 0; attente < limite; attente++ )); do
    restants=0
    for pid in "${pids[@]}"; do
      kill -0 "$pid" 2>/dev/null && restants=1
    done
    (( restants )) || return 0
    sleep 1
  done
  echo "[oscar-chassis] arret force apres ${limite}s" >&2
  kill -KILL "${pids[@]}" 2>/dev/null || true
}
trap cleanup TERM INT EXIT

# L'arret de securite part en premier : il doit veiller avant que le moindre
# pilote ne puisse recevoir une vitesse.
python3 /opt/oscar-chassis/arret_securite.py \
  --topic "${OSCAR_CMD_VEL_TOPIC:-/cmd_vel}" \
  --silence-ms "${OSCAR_WATCHDOG_MS:-300}" &
pids+=($!)

demarrer_bringup

echo "[oscar-chassis] ${#pids[@]} processus en service (arret de securite compris)"

set +e
wait -n "${pids[@]}"
code=$?
set -e
echo "[oscar-chassis] un processus s'est arrete (code=$code), redemarrage supervise" >&2
exit "$code"
