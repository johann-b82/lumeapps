#!/bin/sh
# Nightly pg_dump: plain-format + gzip, atomic rename, 14-day retention.
# Env (from compose): PGHOST, PGUSER, PGPASSWORD, PGDATABASE.
# BACKUP_DIR is overridable for tests only (compose mounts /backups).
set -eu
# Befund 18: die Sicherungen lagen mit 0644 im Verzeichnis — jeder Benutzer
# auf dem Host las die ganze Datenbank. 077 macht daraus 0600.
umask 077
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DATE=$(date +%F)
OUT="${BACKUP_DIR}/kpi-${DATE}.sql.gz"
TMP="${OUT}.tmp"
# A failed or interrupted dump must not leave a full-size .tmp behind — the
# retention find below only matched *.sql.gz, so orphans accumulated forever.
trap 'rm -f "${TMP}"' EXIT
echo "[backup] starting dump -> ${OUT}"
# No `| gzip` pipe: under `set -e` only the LAST pipeline command's status
# counts, so a failing pg_dump used to be renamed into a "successful" backup.
# -Z on plain format gzips the output file itself; gunzip reads it as before.
pg_dump --clean --if-exists --no-owner --no-acl -Fp -Z 6 -f "${TMP}"
mv "${TMP}" "${OUT}"
find "${BACKUP_DIR}" -maxdepth 1 -name 'kpi-*.sql.gz*' -mtime +14 -delete
echo "[backup] wrote ${OUT}"
