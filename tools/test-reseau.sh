#!/bin/bash
# Diagnostic reseau OSCAR — a lancer depuis le poste operateur, sur le reseau
# ou aura lieu la demonstration. Repond a une seule question : la teleoperation
# passera-t-elle depuis ici, et a quelle qualite ?
#
#   ./scripts/test-reseau.sh
#
# Lecture seule cote reseau. Le seul effet de bord est l activation temporaire
# du noeud de sortie Tailscale, remis a l etat initial en fin de script.

set -u
VPS_TS="100.73.151.122"
ROBOT_TS="100.78.49.123"
SP="${TMPDIR:-/tmp}/oscar-nettest"
mkdir -p "$SP"

titre() { echo; echo "=============================================="; echo "$1"; echo "=============================================="; }
ok()    { echo "  [OK]     $1"; }
ko()    { echo "  [ECHEC]  $1"; }
info()  { echo "           $1"; }

titre "1. RESEAU LOCAL"
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
info "adresse locale : ${IP:-inconnue}"

titre "2. UDP SORTANT (ce que WebRTC exige en direct)"
python3 - <<'PY'
import socket, struct, os
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(5)
try:
    s.sendto(struct.pack(">HHI", 1, 0, 0x2112A442) + os.urandom(12), ("stun.l.google.com", 19302))
    d, _ = s.recvfrom(2048)
    print("  [OK]     UDP sortant autorise -> WebRTC direct possible")
except Exception:
    print("  [ECHEC]  UDP sortant bloque -> WebRTC direct impossible")
    print("           il faudra passer par le noeud de sortie Tailscale")
finally:
    s.close()
PY

titre "3. TAILSCALE"
if ! command -v tailscale >/dev/null 2>&1; then
  ko "tailscale absent de cette machine"
  exit 1
fi
ETAT_INITIAL=$(tailscale debug prefs 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('ExitNodeIP') or '')" 2>/dev/null)

if tailscale status >/dev/null 2>&1; then
  ok "connecte au tailnet"
  LIGNE=$(tailscale status 2>/dev/null | grep oscar-vps)
  case "$LIGNE" in
    *direct*) ok "liaison au VPS : DIRECTE (latence minimale)" ;;
    *relay*)  info "liaison au VPS : RELAYEE via DERP"
              info "le reseau bloque l acces direct ; ca fonctionne, mais"
              info "la latence augmente et le debit est reduit" ;;
    *)        info "liaison au VPS : etat indetermine" ;;
  esac
else
  ko "tailscale non connecte — le reseau bloque peut-etre tailscale.com"
  info "sans Tailscale, aucun contournement possible depuis ce reseau"
  exit 1
fi

titre "4. ACCES AUX MACHINES OSCAR"
ping -c 2 -W 3000 "$VPS_TS"   >/dev/null 2>&1 && ok "VPS joignable ($VPS_TS)"     || ko "VPS injoignable"
ping -c 2 -W 3000 "$ROBOT_TS" >/dev/null 2>&1 && ok "robot joignable ($ROBOT_TS)" || ko "robot injoignable (eteint ?)"

titre "5. TELEOPERATION VIA LE NOEUD DE SORTIE"
info "activation du noeud de sortie..."
tailscale set --exit-node="$VPS_TS" >/dev/null 2>&1
sleep 6
SORTIE=$(curl -s --max-time 15 https://api.ipify.org 2>/dev/null)
if [ "$SORTIE" = "51.178.52.131" ]; then
  ok "trafic route par le VPS (IP publique : $SORTIE)"
  python3 - <<'PY'
import socket, struct, os
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(6)
try:
    s.sendto(struct.pack(">HHI", 1, 0, 0x2112A442) + os.urandom(12), ("stun.l.google.com", 19302))
    s.recvfrom(2048)
    print("  [OK]     UDP passe a travers le tunnel -> WebRTC fonctionnel")
except Exception:
    print("  [ECHEC]  UDP toujours bloque malgre le tunnel")
finally:
    s.close()
PY
else
  ko "le noeud de sortie n a pas pris (IP vue : ${SORTIE:-aucune})"
fi

titre "6. REMISE EN ETAT"
if [ -n "$ETAT_INITIAL" ]; then
  tailscale set --exit-node="$ETAT_INITIAL" >/dev/null 2>&1
  info "noeud de sortie restaure : $ETAT_INITIAL"
else
  tailscale set --exit-node= >/dev/null 2>&1
  info "route directe retablie"
fi

titre "VERDICT"
echo "  Si l etape 2 est OK       : rien a faire, tout passe en direct."
echo "  Si 2 echoue mais 5 est OK : lancer avant la demonstration"
echo "                              tailscale up --exit-node=oscar-vps"
echo "  Si 3 ou 5 echoue          : ce reseau bloque aussi Tailscale."
echo "                              Prevoir un partage de connexion mobile."
echo
