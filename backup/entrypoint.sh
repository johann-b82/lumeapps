#!/bin/sh
# Backup sidecar entrypoint — writes crontab, execs crond -f in foreground.
# Per D-02: nightly at 02:00 local time (TZ set by compose service).
set -eu
mkdir -p /etc/crontabs
echo "0 2 * * * /usr/local/bin/dump.sh >> /proc/1/fd/1 2>&1" > /etc/crontabs/root
echo "[backup] crontab installed; starting crond (TZ=${TZ:-UTC})"
exec crond -f -L /dev/stdout
