#!/usr/bin/env bash
# Sante du conteneur : on ne verifie que ce que le bundle a demande.
# Exiger les deux agents alors qu'une composition n'en active qu'un ferait
# declarer malade un runtime parfaitement conforme.
set -uo pipefail

manque=0
verifier() {
  pgrep -f "[${2:0:1}]${2:1}" >/dev/null 2>&1 || { echo "absent: $2" >&2; manque=1; }
}

[[ "${OSCAR_ENABLE_MEDIA:-true}" == true ]] && verifier media oscar_robot_media.py
[[ "${OSCAR_ENABLE_COMMAND:-true}" == true ]] && verifier commande command_agent.py

# Les commandes de mise en route du chassis, si le profil en declare, doivent
# elles aussi tenir : un robot sans pilote moteur n'est pas un robot en service.
for index in $(seq 1 "${OSCAR_BRINGUP_COUNT:-0}"); do
  variable="OSCAR_BRINGUP_${index}"
  commande="${!variable:-}"
  [[ -z "$commande" ]] && continue
  motif="$(printf '%s' "$commande" | awk '{print $NF}')"
  pgrep -f "$motif" >/dev/null 2>&1 || { echo "mise en route absente: $commande" >&2; manque=1; }
done

exit "$manque"
