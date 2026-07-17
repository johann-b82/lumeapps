# E-Mail-Hintergrundmodul (Office 365 / Microsoft Graph)

Zentraler, app-weiter Dienst zum **Versenden von E-Mails** — für Erinnerungen,
Berichte und Benachrichtigungen. Jedes andere Modul (Router oder Service) kann
sich anbinden, ohne selbst SMTP-, OAuth- oder Konfigurationsdetails zu kennen.

- **Transport:** Microsoft Graph API
- **Konfiguration:** zentral auf der `AppSettings`-Singleton-Zeile, gepflegt im
  Admin-Reiter **Einstellungen → E-Mail**
- **Verschlüsselung:** Secret bzw. Refresh-Token liegen Fernet-verschlüsselt in
  der DB, wie alle anderen Zugangsdaten (Personio, ATR, WM)

### Zwei Versandmodi (umschaltbar im Reiter, Feld `email_auth_mode`)

| Modus | Auth | Sendet als | Admin nötig? |
|---|---|---|---|
| **`app`** | OAuth Client-Credentials, App-Berechtigung `Mail.Send` + Admin-Consent | `email_sender_address` (`/users/{sender}/sendMail`) | Ja — einmal Admin-Consent |
| **`delegated`** | Device-Code-Anmeldung mit eigenem M365-Konto, delegiertes `Mail.Send` (Self-Consent) | dem angemeldeten Benutzer (`/me/sendMail`) | Nein für Consent; ggf. einmal für die App-Registrierung |

Für **alle Module ist der Aufruf identisch** — `send_email(...)` wählt den aktiven
Modus automatisch. Der Modus ist jederzeit im Reiter umstellbar.

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

Admin-gate-gesicherte Routen (`app/routers/email.py`). Versand-Routen antworten
mit `{ "ok": bool, "error": str|null }` — ein fehlgeschlagener Versand ist
**HTTP 200 mit `ok=false`**, kein 5xx.

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/api/email/test` | Test-E-Mail an eine Adresse. Body: `{ "to": "name@firma.de" }` |
| `POST` | `/api/email/send` | Generischer Versand. Body: `{ "to": ["…"], "subject": "…", "body_html": "…", "cc"?: […], "body_text"?: "…" }` |
| `POST` | `/api/email/delegated/start` | Delegiert: Device-Code-Anmeldung starten → `{ user_code, verification_uri, device_code, interval, ... }` |
| `POST` | `/api/email/delegated/poll` | Einmal pollen. Body: `{ "device_code": "…" }` → `{ status, account? }` |
| `POST` | `/api/email/delegated/disconnect` | Delegierte Anmeldung vergessen |

---

## Einmalige Einrichtung in Azure / Microsoft Entra

Es gibt zwei Wege — **App-Berechtigung** (zentrales App-Konto, braucht Admin-Consent)
oder **Delegiert** (du meldest dich mit deinem eigenen Konto an, kein Consent nötig).

### Variante A — App-Berechtigung (`email_auth_mode = app`)

Diese Schritte macht **euer Microsoft-365-Administrator**.

1. **App registrieren** — Entra Admin Center → *App registrations* → *New
   registration*. Kontotyp: *Single tenant*. Danach:
   - **Verzeichnis-(Tenant-)ID** → Feld *Tenant-ID*
   - **Anwendungs-(Client-)ID** → Feld *Client-ID*
2. **API-Berechtigung** — *API permissions* → *Add a permission* → *Microsoft
   Graph* → **Application permissions** → **`Mail.Send`** → **„Grant admin
   consent"** (ohne Consent → Versand-403).
3. **Client-Secret** — *Certificates & secrets* → *New client secret*. Den
   **Wert** sofort kopieren → Feld *Client-Secret*. Secrets laufen ab.
4. **Absender** — echtes Postfach im Tenant → Feld *Absenderadresse*.
5. Modus **App-Berechtigung** wählen, **„aktiviert"** setzen, speichern, testen.

> Sicherheits-Tipp: Mit `Mail.Send` (Application) darf die App aus *jedem*
> Postfach senden. Eine **Application Access Policy** in Exchange Online grenzt
> das auf genau das Absenderpostfach ein.

### Variante B — Eigener Account / Delegiert (`email_auth_mode = delegated`)

**Kein Admin-Consent, kein Client-Secret.** Du sendest aus deinem eigenen
Postfach.

1. **App registrieren** (einmalig) — wie oben, aber:
   - *Supported account types*: „Accounts in this organizational directory only".
   - Unter **Authentication** → *Advanced settings* → **„Allow public client
     flows" = Yes** (nötig für den Device-Code-Flow).
   - **Kein** API-Permission-Consent nötig — delegiertes `Mail.Send` genehmigt
     sich der Benutzer beim ersten Login selbst.
   > Falls euer Tenant „Users can register applications" gesperrt hat, legt der
   > Admin **nur** diese Registrierung an (2 Minuten) — Consent/App-Rechte
   > bleiben unnötig.
2. Im Reiter **Tenant-ID** + **Client-ID** eintragen und **speichern**.
3. Modus **„Eigener Account (Delegiert)"** wählen → **„Bei Microsoft anmelden"**.
   Ein Code + Link (`microsoft.com/devicelogin`) erscheint; im Browser öffnen,
   Code eingeben, mit deinem M365-Konto anmelden, delegiertes `Mail.Send`
   bestätigen.
4. Nach „Angemeldet als …" **„aktiviert"** setzen, speichern, testen.

> Der Login liefert ein Refresh-Token (`offline_access`), das verschlüsselt
> gespeichert wird und rotiert — Versand läuft danach dauerhaft im Hintergrund,
> auch für terminierte Erinnerungen. „Verbindung trennen" löscht das Token.

### Fehlerbilder

| Symptom | Ursache |
|---|---|
| `Token-Anforderung fehlgeschlagen (HTTP 401)` | App-Modus: falsche Client-ID/Secret oder Secret abgelaufen |
| `Token-Anforderung fehlgeschlagen (HTTP 400 … tenant)` | falsche Tenant-ID |
| `Versand abgelehnt — fehlende 'Mail.Send'-Berechtigung/Consent` | App-Modus: Admin-Consent fehlt oder Absenderpostfach unbekannt |
| Device-Code startet nicht / `invalid_client` | Delegiert: „Allow public client flows" nicht aktiviert |
| Delegiert-Versand schlägt nach längerer Zeit fehl | Refresh-Token abgelaufen/widerrufen → erneut „Bei Microsoft anmelden" |
| `EmailNotConfigured` | „aktiviert" nicht gesetzt oder ein Pflichtfeld/Token des aktiven Modus fehlt |

---

## Beteiligte Dateien

| Datei | Rolle |
|---|---|
| `backend/app/services/email_service.py` | **Öffentliche API** (`send_email`, `is_configured`) + delegierte Login-Logik — hier binden sich Module an |
| `backend/app/services/graph_client.py` | Graph-Transport (App- + Delegiert-Token, `sendMail`, Device-Code-Flow) |
| `backend/app/routers/email.py` | HTTP-Endpunkte `/api/email/*` |
| `backend/app/models/_base.py` (`AppSettings`) | Konfigurationsspalten `email_*` (inkl. `email_auth_mode`, delegiertes Token) |
| `backend/alembic/versions/v1_82_email_office365.py` | Migration der Spalten |
| `frontend/src/pages/EmailSettingsPage.tsx` | Admin-Reiter mit Modus-Umschalter + Device-Code-Login |
