#!/bin/sh
# Nightly pg_dump: plain-format + gzip, atomic rename, 14-day retention.
# Env (from compose): PGHOST, PGUSER, PGPASSWORD, PGDATABASE.
set -eu
DATE=$(date +%F)
OUT="/backups/kpi-${DATE}.sql.gz"
TMP="${OUT}.tmp"
echo "[backup] starting dump -> ${OUT}"
pg_dump --clean --if-exists --no-owner --no-acl -Fp | gzip -c > "${TMP}"
mv "${TMP}" "${OUT}"
find /backups -maxdepth 1 -name 'kpi-*.sql.gz' -mtime +14 -delete
echo "[backup] wrote ${OUT}"
