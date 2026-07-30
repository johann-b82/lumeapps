# Benutzerverwaltung

## Rollen

Das KPI Dashboard hat drei Rollen:

| Rolle         | Zugriff                                                              |
|---------------|----------------------------------------------------------------------|
| Administrator | Vollzugriff -- Daten hochladen, Einstellungen konfigurieren, Admin Guide einsehen |
| Viewer        | Nur Lese-Zugriff auf Dashboards und User Guide                      |
| QS            | Modul-Zugriff nur auf **FAIR** und **ATR** -- keine Dashboards, keine Einstellungen |

Die Viewer-Rolle hat eine feste UUID: `a2222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb`, die im Skript `bootstrap-roles.sh` waehrend der Erstinstallation gesetzt wird.

## QS-Rolle (nur FAIR + ATR)

Die QS-Rolle ist eine uebergangsweise, fest verdrahtete Rolle fuer die Qualitaetssicherung: Sie gewaehrt Zugriff **ausschliesslich** auf das FAIR- und das ATR-Modul. Dashboards (Vertrieb, HR, Qualitaet, Finanzen, Produktion, Einkauf) und alle Admin-Bereiche bleiben gesperrt.

So richten Sie die QS-Rolle ein:

1. Legen Sie im Directus-Admin-Panel unter **Settings -> Access Control** eine neue Rolle mit dem exakten Namen **`QS`** an (**App Access = ja**, **Admin Access = nein**). Ein abweichender Name wird von der Anwendung beim Login abgelehnt.
2. Geben Sie der QS-Rolle dieselben **Lese-Berechtigungen wie Viewer** auf `directus_users` (eigenes Profil) und `directus_roles` (Feld `name`). Ohne diese Berechtigungen schlaegt der Login fehl.
3. Kopieren Sie die UUID der neuen Rolle und setzen Sie sie als `DIRECTUS_QS_ROLE_UUID` in Ihrer `.env`-Datei. Ohne diese Variable ist die QS-Rolle deaktiviert.
4. Legen Sie unter **Users** einen Benutzer an und weisen Sie ihm die Rolle **QS** zu.

> **Hinweis:** Diese Rolle ist ein Uebergang bis zum geplanten AD-basierten Rechtesystem.

## Benutzer erstellen

1. Oeffnen Sie das Directus-Admin-Panel unter `http://localhost:8055`.
2. Melden Sie sich mit den Zugangsdaten aus Ihrer `.env`-Datei an (`DIRECTUS_ADMIN_EMAIL` / `DIRECTUS_ADMIN_PASSWORD`).
3. Navigieren Sie zu **Users** in der linken Seitenleiste.
4. Klicken Sie auf **+ New User**.
5. Legen Sie **E-Mail**, **Passwort** und **Rolle** (Administrator, Viewer oder QS) des Benutzers fest.
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
