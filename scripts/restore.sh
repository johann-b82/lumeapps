#!/bin/sh
# ./scripts/restore.sh <dump-file>
# Streams a dump file (.sql or .sql.gz) into the running `db` compose service.
# Idempotent via pg_dump --clean --if-exists semantics in the dump itself.
set -eu

if [ $# -ne 1 ]; then
  echo "usage: $0 <dump-file>" >&2
  exit 2
fi

DUMP="$1"
if [ ! -f "$DUMP" ]; then
  echo "not found: $DUMP" >&2
  exit 1
fi

# Always operate from repo root so `docker compose` resolves.
cd "$(dirname "$0")/.."

case "$DUMP" in
  *.gz) STREAM="gunzip -c" ;;
  *)    STREAM="cat" ;;
esac

echo "[restore] source: $DUMP"
echo "[restore] target: db container, database \$POSTGRES_DB"
echo "[restore] THIS WILL REPLACE data in the target database. Ctrl-C within 5s to abort."
sleep 5

$STREAM "$DUMP" | docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'

echo "[restore] done"
