#!/usr/bin/env bash
# Guard E (Log-Hygiene): Verhindert, dass die Log-Schreiblast wieder anwächst.
#
# Hintergrund: Auf 192.9.201.9 lief die Platte voll, weil Caddy jeden Request
# (inkl. hunderter Vite-Modul-Requests pro Seitenaufruf) und Uvicorn jeden
# /health-, Playlist- und Heartbeat-Aufruf der Pis ins Container-Log schrieb.
# Docker rotiert json-file-Logs nur nach Größe — ohne Cap wächst eine Datei
# unbegrenzt. Dieser Guard prüft die Stellen, die das verhindern:
#
#   1. docker-compose.yml — JEDER Dienst trägt `logging: *default-logging`
#                          (auch die One-Shot-Dienste: jeder `compose up`
#                          erzeugt einen neuen Container mit eigener Logdatei)
#   2. docker-compose.yml — max-size höchstens 10m, max-file höchstens 3
#   3. docker-compose.yml — uvicorn-Kommando enthält --no-access-log
#   4. backend/Dockerfile  — CMD enthält --no-access-log
#   5. caddy/Caddyfile     — log-Block hat `level ERROR` (kein Access-Log
#                          für erfolgreiche Requests)
#   6. scripts/systemd/signage-sidecar.service — uvicorn ohne Access-Log
#      (Pi-journald auf 16-GB-SD-Karte)
#
# Usage: bash scripts/ci/check_log_hygiene.sh
#   (Braucht kein docker compose — liest nur Dateien)
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
DOCKERFILE="backend/Dockerfile"
CADDYFILE="caddy/Caddyfile"
# Das Produktions-Overlay bringt eine eigene Caddy-Konfiguration und ein
# eigenes uvicorn-Kommando mit. Ohne diese Zeilen liefe der Guard an genau der
# Datei vorbei, die auf dem Server gilt.
CADDYFILE_PROD="caddy/Caddyfile.prod"
COMPOSE_PROD="docker-compose.prod.yml"
SIDECAR_UNIT="scripts/systemd/signage-sidecar.service"

failures=()

# --- 1. Jeder Compose-Dienst hat den Logging-Anker -------------------------
# Dienste stehen unter `services:` mit zwei Leerzeichen Einrückung. Wir
# sammeln Dienstnamen und prüfen, ob im jeweiligen Block `logging:` vorkommt.
services=$(awk '
  /^services:/ { in_services=1; next }
  in_services && /^[^ ]/ { in_services=0 }
  in_services && /^  [a-zA-Z0-9_-]+:/ { sub(/:.*/, ""); sub(/^  /, ""); print }
' "$COMPOSE_FILE")

for svc in $services; do
  block=$(awk -v svc="$svc" '
    $0 ~ "^  " svc ":" { in_block=1; next }
    in_block && /^  [a-zA-Z0-9_-]+:/ { in_block=0 }
    in_block { print }
  ' "$COMPOSE_FILE")
  if ! grep -qE '^[[:space:]]+logging: \*default-logging' <<<"$block"; then
    failures+=("$COMPOSE_FILE: Dienst '$svc' hat kein 'logging: *default-logging'")
  fi
done

# --- 2. Rotationsgrenzen -----------------------------------------------------
max_size=$(grep -E '^[[:space:]]+max-size:' "$COMPOSE_FILE" | head -1 | grep -oE '[0-9]+' || true)
max_file=$(grep -E '^[[:space:]]+max-file:' "$COMPOSE_FILE" | head -1 | grep -oE '[0-9]+' || true)
if [ -z "$max_size" ] || [ "$max_size" -gt 10 ]; then
  failures+=("$COMPOSE_FILE: x-logging max-size muss <= 10m sein (ist: '${max_size:-unset}')")
fi
if [ -z "$max_file" ] || [ "$max_file" -gt 3 ]; then
  failures+=("$COMPOSE_FILE: x-logging max-file muss <= 3 sein (ist: '${max_file:-unset}')")
fi

# --- 3./4. Uvicorn ohne Access-Log ------------------------------------------
if ! grep -qE 'uvicorn.*--no-access-log' "$COMPOSE_FILE"; then
  failures+=("$COMPOSE_FILE: uvicorn-Kommando ohne --no-access-log")
fi
if ! grep -qE '"--no-access-log"' "$DOCKERFILE"; then
  failures+=("$DOCKERFILE: CMD ohne --no-access-log")
fi

# --- 5. Caddy: nur Fehler loggen ---------------------------------------------
for cf in "$CADDYFILE" "$CADDYFILE_PROD"; do
  [ -f "$cf" ] || continue
  if ! awk '/^[[:space:]]*log \{/,/^[[:space:]]*\}/' "$cf" | grep -qE '^[[:space:]]*level ERROR'; then
    failures+=("$cf: log-Block ohne 'level ERROR'")
  fi
done

# --- 5b. Produktions-Overlay: uvicorn ohne Access-Log, ohne --reload ---------
if [ -f "$COMPOSE_PROD" ]; then
  if grep -qE '^[[:space:]]*command:.*uvicorn' "$COMPOSE_PROD"; then
    if ! grep -E '^[[:space:]]*command:.*uvicorn' "$COMPOSE_PROD" | grep -q -- '--no-access-log'; then
      failures+=("$COMPOSE_PROD: uvicorn ohne --no-access-log")
    fi
    if grep -E '^[[:space:]]*command:.*uvicorn' "$COMPOSE_PROD" | grep -q -- '--reload'; then
      failures+=("$COMPOSE_PROD: uvicorn mit --reload (kappt im Betrieb jeden Player-Stream)")
    fi
  fi
fi

# --- 6. Pi-Sidecar ohne Access-Log -------------------------------------------
if ! grep -q -- '--no-access-log' "$SIDECAR_UNIT"; then
  failures+=("$SIDECAR_UNIT: uvicorn ohne --no-access-log")
fi

if [ "${#failures[@]}" -gt 0 ]; then
  echo "FAIL: Guard E — Log-Hygiene verletzt (Platte-voll-Vorfall 2026)"
  for f in "${failures[@]}"; do
    echo "  - $f"
  done
  exit 1
fi

echo "PASS: Guard E — Log-Hygiene (Rotation, Access-Logs, Caddy-Level) in Ordnung"
