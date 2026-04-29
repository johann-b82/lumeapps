# Benutzerverwaltung

## Rollen

Das KPI Dashboard hat zwei Rollen:

| Rolle         | Zugriff                                                              |
|---------------|----------------------------------------------------------------------|
| Administrator | Vollzugriff -- Daten hochladen, Einstellungen konfigurieren, Admin Guide einsehen |
| Viewer        | Nur Lese-Zugriff auf Dashboards und User Guide                      |

Die Viewer-Rolle hat eine feste UUID: `a2222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb`, die im Skript `bootstrap-roles.sh` waehrend der Erstinstallation gesetzt wird.

## Benutzer erstellen

1. Oeffnen Sie das Directus-Admin-Panel unter `http://localhost:8055`.
2. Melden Sie sich mit den Zugangsdaten aus Ihrer `.env`-Datei an (`DIRECTUS_ADMIN_EMAIL` / `DIRECTUS_ADMIN_PASSWORD`).
3. Navigieren Sie zu **Users** in der linken Seitenleiste.
4. Klicken Sie auf **+ New User**.
5. Legen Sie **E-Mail**, **Passwort** und **Rolle** (Administrator oder Viewer) des Benutzers fest.
6. Klicken Sie auf **Save**.

Der neue Benutzer kann sich nun mit der zugewiesenen Rolle am KPI Dashboard anmelden.

## Benutzer befoerdern

1. Oeffnen Sie das Directus-Admin-Panel unter `http://localhost:8055`.
2. Navigieren Sie zu **Users** in der linken Seitenleiste und waehlen Sie den Benutzer aus.
3. Aendern Sie das Feld **Role** auf **Administrator**.
4. Klicken Sie auf **Save**.

> **Tipp:** Rollenaenderungen werden beim naechsten Login des Benutzers wirksam. Wenn der Benutzer derzeit angemeldet ist, muss er sich ab- und wieder anmelden, um die neuen Berechtigungen zu sehen.

## Administrator-Rollen-UUID

Die Administrator-Rollen-UUID wird von Directus beim ersten Start generiert und ist nicht fest wie die Viewer-Rolle. Sie muessen sie abrufen und als `DIRECTUS_ADMINISTRATOR_ROLE_UUID` in Ihrer `.env`-Datei setzen, damit die Anwendung Administratoren korrekt erkennt.

Lesen Sie den Artikel [System Setup](/docs/admin-guide/system-setup) fuer Anweisungen zum Abrufen der Administrator-Rollen-UUID waehrend der Erstinstallation.

## Verwandte Artikel

- [System Setup](/docs/admin-guide/system-setup) -- Erstinstallation und Umgebungskonfiguration
- [Daten hochladen](/docs/user-guide/uploading-data) -- nur Administratoren koennen Datendateien hochladen

> **Hinweis:** Speichern Sie `DIRECTUS_ADMIN_PASSWORD` in einem Passwort-Manager. Teilen Sie es nicht per E-Mail oder Chat.
