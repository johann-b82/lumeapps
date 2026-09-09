# certs/

Hier lag bis 2026-09-09 ein mkcert-Entwicklungszertifikat **samt privatem Schlüssel** im Repo (Befund 12 in `docs/security-findings.md`). Es war nirgends eingebunden — weder in `docker-compose.yml` noch im `Caddyfile` — und ist entfernt.

Zwei Dinge dazu:

1. **Der Schlüssel steht weiterhin in der Git-Historie** (seit dem ersten Commit). Ein `git rm` löscht ihn nicht rückwirkend. Falls das Zertifikat je auf einem erreichbaren Host ausgeliefert wurde, gilt es als kompromittiert und muss ersetzt werden. Ausgestellt auf `O=mkcert development certificate`, gültig bis Juli 2028.
2. **TLS-Material kommt je Umgebung von außen**, nicht aus dem Repo. Auf dem Host unter `/srv/acm/certs` ablegen und in Caddy per Pfad einbinden; das Verzeichnis ist in `.gitignore`.
