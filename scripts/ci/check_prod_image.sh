#!/usr/bin/env bash
# Guard F (Befund 20): Das Produktionsbild bleibt ohne Entwicklungswerkzeuge
# und ohne Testsuite.
#
# Drei Dinge halten das zusammen, und jedes davon bricht still:
#
#   1. backend/Dockerfile endet mit dem Ziel `entwicklung`. Ohne `target:`
#      baut Docker das LETZTE Ziel — Entwicklung und CI hängen daran.
#      Käme `produktion` ans Ende, liefe die CI plötzlich ohne pytest.
#   2. docker-compose.prod.yml baut `target: produktion` für api und migrate.
#      Fehlt das, geht das Entwicklungsbild in den Betrieb.
#   3. backend/.dockerignore schließt tests/ aus. Sonst liegt die Suite samt
#      dem Helfer, der Directus-Token ausstellt, im Produktionsbild.
#
# Usage: bash scripts/ci/check_prod_image.sh
#   (Braucht kein docker — liest nur Dateien)
set -euo pipefail

DOCKERFILE="backend/Dockerfile"
DOCKERIGNORE="backend/.dockerignore"
COMPOSE_PROD="docker-compose.prod.yml"

failures=()

# --- 1. Letztes Ziel im Dockerfile ist `entwicklung` -------------------------
letztes_ziel=$(grep -E '^FROM .* AS ' "$DOCKERFILE" | tail -1 | awk '{print $NF}')
if [ "$letztes_ziel" != "entwicklung" ]; then
  failures+=("$DOCKERFILE: letztes Ziel ist '$letztes_ziel', erwartet 'entwicklung' (ohne target: baut Docker das letzte)")
fi
if ! grep -qE '^FROM .* AS produktion$' "$DOCKERFILE"; then
  failures+=("$DOCKERFILE: kein Ziel 'produktion'")
fi

# --- 2. Overlay baut das Produktionsziel -------------------------------------
for dienst in api migrate; do
  block=$(awk -v d="$dienst" '
    $0 ~ "^  " d ":" { in_block=1; next }
    in_block && /^  [a-zA-Z0-9_-]+:/ { in_block=0 }
    in_block { print }
  ' "$COMPOSE_PROD")
  if ! grep -qE '^[[:space:]]+target: produktion' <<<"$block"; then
    failures+=("$COMPOSE_PROD: Dienst '$dienst' baut nicht 'target: produktion'")
  fi
done

# --- 3. Testsuite ist vom Bild ausgeschlossen --------------------------------
if [ ! -f "$DOCKERIGNORE" ]; then
  failures+=("$DOCKERIGNORE fehlt — die Testsuite landet im Produktionsbild")
elif ! grep -qE '^tests/?$' "$DOCKERIGNORE"; then
  failures+=("$DOCKERIGNORE: 'tests/' fehlt")
fi

if [ "${#failures[@]}" -gt 0 ]; then
  echo "FAIL: Guard F — Produktionsbild (Befund 20)"
  for f in "${failures[@]}"; do
    echo "  - $f"
  done
  exit 1
fi

echo "PASS: Guard F — Produktionsbild ohne Entwicklungswerkzeuge und Testsuite"
