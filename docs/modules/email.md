# E-Mail-Hintergrundmodul (Office 365 / Microsoft Graph)

Zentraler, app-weiter Dienst zum **Versenden von E-Mails** — für Erinnerungen,
Berichte und Benachrichtigungen. Jedes andere Modul (Router oder Service) kann
sich anbinden, ohne selbst SMTP-, OAuth- oder Konfigurationsdetails zu kennen.

- **Transport:** Microsoft Graph API (`/users/{sender}/sendMail`)
- **Auth:** OAuth 2.0 Client-Credentials (App-Berechtigung `Mail.Send`)
- **Konfiguration:** zentral auf der `AppSettings`-Singleton-Zeile, gepflegt im
  Admin-Reiter **Einstellungen → E-Mail**
- **Verschlüsselung:** Client-Secret liegt Fernet-verschlüsselt in der DB
  (`email_client_secret_enc`), wie alle anderen Zugangsdaten (Personio, ATR, WM)

---

## So bindet sich ein anderes Modul an

Ein einziger Import genügt. Die Funktion lädt die Konfiguration selbst aus der
`AppSettings`-Zeile, baut den Graph-Client und versendet.

```python
from app.services.email_service import (
    send_email,
    EmailNotConfigured,
    EmailSendError,
)

async def notify(session):
    try:
        await send_email(
            session,
            to="team@firma.de",                 # str oder list[str]
            subject="Wöchentlicher KPI-Bericht",
            body_html="<h1>Bericht</h1><p>…</p>",
            # optional:
            # body_text="Nur-Text-Alternative",
            # cc=["chef@firma.de"],
        )
    except EmailNotConfigured:
        ...  # Modul deaktiviert / Zugangsdaten unvollständig — bewusst tolerieren
    except EmailSendError as exc:
        ...  # Graph hat abgelehnt oder war nicht erreichbar — loggen/erneut versuchen
```

### Funktions-Contract

```python
async def send_email(
    session: AsyncSession,
    *,
    to: str | list[str],
    subject: str,
    body_html: str,
    body_text: str | None = None,
    cc: str | list[str] | None = None,
) -> None
```

- **`session`** — eine offene `AsyncSession`; wird nur zum Lesen der Settings-Zeile
  genutzt. Übergib deine vorhandene Session (aus `Depends(get_async_db_session)`
  oder `AsyncSessionLocal()` im Scheduler).
- **Erfolg:** kehrt ohne Rückgabewert zurück (Graph antwortet mit `202 Accepted`).
- **Fehler:** wirft `EmailNotConfigured` oder `EmailSendError` (beide erben von
  `EmailError`). **Fange sie ab** — ein fehlgeschlagener Versand darf deinen
  eigentlichen Ablauf (z. B. einen Sync-Job) nicht abbrechen.

### Vorher prüfen, ob konfiguriert

Wenn du eine teure Nachricht (großer Bericht) nur bauen willst, falls Versand
überhaupt möglich ist:

```python
from app.services.email_service import is_configured

if await is_configured(session):
    html = build_expensive_report(...)
    await send_email(session, to=..., subject=..., body_html=html)
```

`is_configured` ist `True`, wenn das Modul **aktiviert** ist **und** alle
Pflicht-Zugangsdaten vorhanden sind.

---

## Als terminierte Erinnerung (Scheduler)

Erinnerungen werden über den bestehenden APScheduler in
[`app/scheduler.py`](../../backend/app/scheduler.py) angebunden — dieselbe
Mechanik wie Personio-Sync und Sensor-Polling. Muster für einen wöchentlichen
Bericht:

```python
# in app/scheduler.py
from apscheduler.triggers.cron import CronTrigger

async def _run_weekly_report() -> None:
    async with AsyncSessionLocal() as session:
        try:
            from app.services.email_service import send_email, EmailError
            html = await build_report(session)          # dein Modul liefert den Inhalt
            await send_email(session, to="team@firma.de",
                             subject="Wochenbericht", body_html=html)
        except EmailError:
            log.exception("weekly_report email failed")   # nie den Scheduler killen

# in der lifespan-Funktion, bei den anderen add_job(...)-Aufrufen:
scheduler.add_job(
    _run_weekly_report,
    trigger=CronTrigger(day_of_week="mon", hour=6, minute=0, timezone=timezone.utc),
    id="weekly_report", replace_existing=True,
    max_instances=1, coalesce=True, misfire_grace_time=300,
)
```

> Deployment-Invariante: der API-Container läuft mit `--workers 1`
> (siehe `docker-compose.yml`), damit Scheduler-Jobs nicht mehrfach feuern.

---

## HTTP-Endpunkte (admin-only)

Für Ad-hoc-Versand oder ein Frontend gibt es zwei admin-gate-gesicherte Routen
(`app/routers/email.py`). Beide antworten mit `{ "ok": bool, "error": str|null }`
— ein fehlgeschlagener Versand ist **HTTP 200 mit `ok=false`**, kein 5xx.

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/api/email/test` | Test-E-Mail an eine Adresse — verifiziert das O365-Setup. Body: `{ "to": "name@firma.de" }` |
| `POST` | `/api/email/send` | Generischer Versand. Body: `{ "to": ["…"], "subject": "…", "body_html": "…", "cc"?: […], "body_text"?: "…" }` |

---

## Einmalige Einrichtung in Azure / Microsoft Entra

Diese Schritte macht **euer Microsoft-365-Administrator** (Claude kann keine
Azure-App-Registrierung anlegen). Ergebnis sind vier Werte, die anschließend im
Admin-Reiter **Einstellungen → E-Mail** eingetragen werden.

1. **App registrieren** — Entra Admin Center → *App registrations* → *New
   registration*. Name z. B. „LumeApps Mailer". Kontotyp: *Single tenant*.
   Nach dem Anlegen findest du:
   - **Verzeichnis-(Tenant-)ID** → Feld *Tenant-ID*
   - **Anwendungs-(Client-)ID** → Feld *Client-ID*
2. **API-Berechtigung** — *API permissions* → *Add a permission* → *Microsoft
   Graph* → **Application permissions** → **`Mail.Send`** hinzufügen.
   Anschließend **„Grant admin consent"** klicken (Pflicht — ohne Consent
   schlägt der Versand mit 403 fehl).
3. **Client-Secret** — *Certificates & secrets* → *New client secret*. Den
   **Wert** (nicht die Secret-ID!) sofort kopieren → Feld *Client-Secret*.
   Secrets laufen ab; bei Ablauf ein neues erzeugen und im Reiter erneut
   eintragen.
4. **Absender** — die *Absender-E-Mailadresse* muss ein echtes Postfach im
   Tenant sein (Benutzer- oder freigegebenes Postfach). Trag sie im Reiter ein,
   optional einen Absendernamen.
5. Häkchen **„E-Mail-Versand aktiviert"** setzen, speichern und über
   **„Test-E-Mail senden"** prüfen.

> Sicherheits-Tipp: Mit der Application-Permission `Mail.Send` darf die App aus
> *jedem* Postfach senden. Wer das einschränken will, richtet in Exchange Online
> eine **Application Access Policy** ein, die die App auf genau dieses eine
> Absenderpostfach begrenzt.

### Fehlerbilder

| Symptom | Ursache |
|---|---|
| `Token-Anforderung fehlgeschlagen (HTTP 401)` | falsche Client-ID/Secret oder Secret abgelaufen |
| `Token-Anforderung fehlgeschlagen (HTTP 400 … tenant)` | falsche Tenant-ID |
| `Versand abgelehnt — fehlende 'Mail.Send'-Berechtigung/Consent` | Admin-Consent fehlt oder Absenderpostfach unbekannt |
| `EmailNotConfigured` | Häkchen „aktiviert" nicht gesetzt oder ein Pflichtfeld leer |

---

## Beteiligte Dateien

| Datei | Rolle |
|---|---|
| `backend/app/services/email_service.py` | **Öffentliche API** (`send_email`, `is_configured`) — hier binden sich Module an |
| `backend/app/services/graph_client.py` | Graph-Transport (Token + `sendMail`) |
| `backend/app/routers/email.py` | HTTP-Endpunkte `/api/email/test` und `/api/email/send` |
| `backend/app/models/_base.py` (`AppSettings`) | Konfigurationsspalten `email_*` |
| `backend/alembic/versions/v1_82_email_office365.py` | Migration der Spalten |
| `frontend/src/pages/EmailSettingsPage.tsx` | Admin-Reiter |
