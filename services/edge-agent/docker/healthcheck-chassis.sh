#!/usr/bin/env bash
# Sante du conteneur chassis : l'arret de securite et chaque mise en route
# declaree doivent tenir. Un robot sans pilote moteur, ou sans arret de
# securite, n'est pas un robot en service.
set -uo pipefail

manque=0
pgrep -f "[a]rret_securite.py" >/dev/null 2>&1 || { echo "arret de securite absent" >&2; manque=1; }

for index in $(seq 1 "${OSCAR_BRINGUP_COUNT:-0}"); do
  variable="OSCAR_BRINGUP_${index}"
  commande="${!variable:-}"
  [[ -z "$commande" ]] && continue
  motif="$(printf '%s' "$commande" | awk '{print $NF}')"
  pgrep -f "$motif" >/dev/null 2>&1 || { echo "mise en route absente: $commande" >&2; manque=1; }
done

exit "$manque"
