"""CI-Wächter: jede /api/*-Route ist admin-gesichert oder ausdrücklich gelistet.

Generalization of test_sensors_admin_gate.py per Phase B of
docs/superpowers/specs/2026-04-28-backend-router-compute-crud-cleanup-design.md.

Die Listen stehen als Literale in dieser Datei, damit jede Ergänzung durch
eine Prüfung geht.

Befund 11 der Sicherheitsanalyse: vorher gab es *eine* Liste, und ein
Eintrag darin hieß „nicht weiter hinsehen". Eine Route konnte ihre
Authentifizierung verlieren, ohne dass hier etwas rot wurde. Jetzt sagt
jeder Eintrag, *welche* Sicherung die Route trägt, und der Wächter prüft
genau die:

  * ``OEFFENTLICH``  — gar keine Sicherung, mit Begründung je Eintrag
  * ``GERAET``       — Geräte-JWT (Signage-Player), keine Nutzerrolle
  * ``ANGEMELDET``   — angemeldeter Nutzer, aber nicht zwingend Admin

Dazu wird je Methode geprüft: eine Route mit ``methods={"GET", "POST"}``
muss für jede ihrer Methoden gelistet sein. Vorher genügte ein Eintrag für
eine davon, und die andere fiel still durch.
"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app
from app.security.device_auth import get_current_device
from app.security.directus_auth import get_current_user, require_admin, require_atr_fair


# --- Öffentlich: bewusst ohne jede Sicherung --------------------------------
# Jeder Eintrag braucht einen Grund, warum hier niemand angemeldet sein kann.
OEFFENTLICH: set[tuple[str, frozenset[str]]] = {
    # Logo für Anmeldeseite und Kiosk — vor der Anmeldung sichtbar.
    ("/api/settings/logo/public", frozenset({"GET"})),
    # HR-Kiosk-Einbettungen: ein Bildschirm im Flur hat keine Sitzung. Die
    # Nutzlast trägt nur, was das Board malt — kein Geburtsdatum, kein Alter,
    # und der Foto-Weg antwortet nur für gerade gezeigte Personen.
    # Siehe routers/hr_embed.py.
    ("/api/hr/embed/birthdays/this-week", frozenset({"GET"})),
    ("/api/hr/embed/joiners/recent", frozenset({"GET"})),
    ("/api/hr/embed/employees/{employee_id}/photo", frozenset({"GET"})),
    # WM-Kiosk-Einbettungen, gleiche Begründung. Der football-data.org-
    # Schlüssel verlässt den Server nicht. Siehe routers/worldcup.py.
    ("/api/worldcup/embed/today", frozenset({"GET"})),
    ("/api/worldcup/embed/standings", frozenset({"GET"})),
    ("/api/worldcup/embed/matches", frozenset({"GET"})),
    ("/api/worldcup/embed/knockout", frozenset({"GET"})),
    ("/api/worldcup/embed/scorers", frozenset({"GET"})),
    ("/api/worldcup/embed/tippspiel", frozenset({"GET"})),
    # Ein ungekoppelter Bildschirm hat noch kein Token vorzuzeigen.
    ("/api/signage/pair/request", frozenset({"POST"})),
    ("/api/signage/pair/status", frozenset({"GET"})),
    # Caddys `forward_auth`-Ziel — dieser Endpunkt IST die Authentifizierung,
    # Caddy ruft ihn mit dem eingehenden Cookie. Seit v1.84 ungenutzt.
    # Siehe app/routers/auth_forward.py.
    ("/api/auth/forward", frozenset({"GET"})),
    # Einmalhelfer, der abgelaufene Directus-Cookies verfallen lässt. Genau
    # dann aufgerufen, wenn niemand angemeldet ist; einzige Wirkung Set-Cookie.
    ("/api/auth/clear-cookies", frozenset({"GET"})),
}

# --- Geräte-JWT: Signage-Player, keine Nutzerrolle --------------------------
GERAET: set[tuple[str, frozenset[str]]] = {
    ("/api/signage/player/playlist", frozenset({"GET"})),
    ("/api/signage/player/heartbeat", frozenset({"POST"})),
    ("/api/signage/player/stream", frozenset({"GET"})),
    ("/api/signage/player/asset/{media_id}", frozenset({"GET"})),
    ("/api/signage/player/asset/{media_id}/slide/{idx}", frozenset({"GET"})),
    ("/api/signage/player/calibration", frozenset({"GET"})),
}

# --- Angemeldet, aber nicht zwingend Admin ----------------------------------
# Lesewege der Dashboards. Jeder Eintrag muss `get_current_user` tragen —
# fällt die Sicherung weg, wird dieser Wächter rot.
ANGEMELDET: set[tuple[str, frozenset[str]]] = {
    # Einstellungen: Lesen für Viewer, Schreiben admin-gesichert
    # (mixed-gate-Router; siehe settings.py-Docstring).
    ("/api/settings", frozenset({"GET"})),
    ("/api/settings/logo", frozenset({"GET"})),
    ("/api/settings/personio-options", frozenset({"GET"})),
    # KPI-Dashboard.
    ("/api/kpis", frozenset({"GET"})),
    ("/api/kpis/chart", frozenset({"GET"})),
    ("/api/kpis/latest-upload", frozenset({"GET"})),
    # HR-KPIs.
    ("/api/hr/kpis", frozenset({"GET"})),
    ("/api/hr/kpis/history", frozenset({"GET"})),
    ("/api/data/employees/overtime", frozenset({"GET"})),
    # HR-Startseite und Organigramm.
    ("/api/hr/birthdays/this-week", frozenset({"GET"})),
    ("/api/hr/joiners/recent", frozenset({"GET"})),
    ("/api/hr/employees/{employee_id}/photo", frozenset({"GET"})),
    ("/api/hr/org-chart", frozenset({"GET"})),
    # Vertriebsaktivität (v1.41).
    ("/api/data/sales/contacts-weekly", frozenset({"GET"})),
    ("/api/data/sales/orders-distribution", frozenset({"GET"})),
    ("/api/data/sales/customer-share", frozenset({"GET"})),
    # Einkauf / OTD (v1.60).
    ("/api/procurement/otd", frozenset({"GET"})),
    ("/api/procurement/otd/history", frozenset({"GET"})),
    ("/api/procurement/otd/list", frozenset({"GET"})),
    # Ladenhüter (v1.106).
    ("/api/procurement/stock-orders/top", frozenset({"GET"})),
    # Produktion / Aufträge in Verzug (v1.76).
    ("/api/production/verzug", frozenset({"GET"})),
    ("/api/production/verzug/history", frozenset({"GET"})),
    ("/api/production/verzug/list", frozenset({"GET"})),
    ("/api/production/verzug/overdue", frozenset({"GET"})),
    # Qualität (PATCH bookings/{id} bleibt Admin, siehe Docstring).
    ("/api/quality/audit-findings", frozenset({"GET"})),
    ("/api/quality/audit-findings/list", frozenset({"GET"})),
    ("/api/quality/audit-findings/history", frozenset({"GET"})),
    ("/api/quality/complaint-rate", frozenset({"GET"})),
    ("/api/quality/complaint-rate/history", frozenset({"GET"})),
    ("/api/quality/complaints/list", frozenset({"GET"})),
    ("/api/quality/inspections", frozenset({"GET"})),
    ("/api/quality/inspections/history", frozenset({"GET"})),
    ("/api/quality/inspections/list", frozenset({"GET"})),
    ("/api/quality/inspections/bookings", frozenset({"GET"})),
    # Finanzperspektive.
    ("/api/finance/material-cost-ratio", frozenset({"GET"})),
    ("/api/finance/material-cost-ratio/history", frozenset({"GET"})),
    ("/api/finance/material-cost-ratio/list", frozenset({"GET"})),
    ("/api/finance/personnel-cost-ratio", frozenset({"GET"})),
    ("/api/finance/personnel-cost-ratio/history", frozenset({"GET"})),
    ("/api/finance/personnel-cost-ratio/list", frozenset({"GET"})),
    # Aktualität der Synchronisierung (mixed-gate; siehe sync.py-Docstring).
    ("/api/sync/meta", frozenset({"GET"})),
    # KPI-Bewertung und Maßnahmen — Lesen für Dashboard-Leser, Schreiben Admin.
    ("/api/kpi-review/registry", frozenset({"GET"})),
    ("/api/kpi-review/summary", frozenset({"GET"})),
    ("/api/kpi-review/comments", frozenset({"GET"})),
    ("/api/kpi-review/measures", frozenset({"GET"})),
    # Seiten-Feedback abgeben darf jede angemeldete Rolle; Liste, Screenshot,
    # Änderung und Löschen bleiben Admin. Siehe routers/feedback.py.
    ("/api/feedback", frozenset({"POST"})),
    # Newsletter lesen (mixed-gate-Router; Schreibwege tragen require_admin).
    ("/api/newsletter", frozenset({"GET"})),
    ("/api/newsletter/rubriken", frozenset({"GET"})),
    ("/api/newsletter/{ausgabe_id}", frozenset({"GET"})),
    ("/api/newsletter/{ausgabe_id}/cover", frozenset({"GET"})),
    ("/api/newsletter/{ausgabe_id}/rueckseite", frozenset({"GET"})),
    ("/api/newsletter/eintrag/{eintrag_id}/bild", frozenset({"GET"})),
    ("/api/newsletter/eintrag-bild/{bild_id}", frozenset({"GET"})),
    # Belegschafts-KPI.
    ("/api/hr/belegschaft-kpi", frozenset({"GET"})),
    ("/api/hr/belegschaft-kpi/meta", frozenset({"GET"})),
}

#: Nur für ältere Verweise — die Vereinigung aller drei Listen.
ADMIN_GATE_ALLOWLIST: set[tuple[str, frozenset[str]]] = OEFFENTLICH | GERAET | ANGEMELDET


def _walk_deps(deps):
    out = []
    for d in deps:
        out.append(d.call)
        out.extend(_walk_deps(d.dependencies))
    return out


def _api_routen() -> list[APIRoute]:
    routen = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/")
    ]
    assert routen, "keine /api/*-Route registriert — fehlt ein include_router?"
    return routen


def _eintraege(route: APIRoute) -> set[tuple[str, frozenset[str]]]:
    """Je Methode ein Eintrag — eine Route mit zwei Methoden braucht zwei."""
    return {(route.path, frozenset({m})) for m in route.methods if m != "HEAD"}


def test_every_api_route_is_admin_gated_or_allowlisted():
    """Jede Methode jeder Route ist admin-gesichert oder ausdrücklich gelistet."""
    gelistet = {
        (pfad, frozenset({m}))
        for pfad, methoden in ADMIN_GATE_ALLOWLIST
        for m in methoden
    }

    violations: list[str] = []
    for route in _api_routen():
        all_calls = _walk_deps(route.dependant.dependencies)
        # ATR + FAIR tragen require_atr_fair (Admin + Übergangsrolle QS)
        # statt require_admin; beide sperren Viewer aus.
        if require_admin in all_calls or require_atr_fair in all_calls:
            continue
        for eintrag in _eintraege(route) - gelistet:
            violations.append(f"{sorted(eintrag[1])} {eintrag[0]}")

    assert not violations, (
        "diese /api/*-Methoden sind weder admin-gesichert noch gelistet:\n  - "
        + "\n  - ".join(sorted(violations))
    )


def test_gelistete_routen_tragen_die_sicherung_die_ihre_liste_verspricht():
    """Befund 11: ein Eintrag sagt, *welche* Sicherung gilt — und die wird geprüft."""
    nach_eintrag = {}
    for route in _api_routen():
        for eintrag in _eintraege(route):
            nach_eintrag[eintrag] = _walk_deps(route.dependant.dependencies)

    fehler: list[str] = []

    def _je_methode(liste):
        return {(p, frozenset({m})) for p, methoden in liste for m in methoden}

    for eintrag in _je_methode(OEFFENTLICH):
        calls = nach_eintrag.get(eintrag)
        if calls is None:
            continue
        for gate in (get_current_user, get_current_device, require_admin, require_atr_fair):
            if gate in calls:
                fehler.append(
                    f"OEFFENTLICH {eintrag[0]} trägt {gate.__name__} — "
                    "Eintrag in die passende Liste verschieben"
                )

    for eintrag in _je_methode(GERAET):
        calls = nach_eintrag.get(eintrag)
        if calls is None:
            continue
        if get_current_device not in calls:
            fehler.append(f"GERAET {eintrag[0]} ohne get_current_device")

    for eintrag in _je_methode(ANGEMELDET):
        calls = nach_eintrag.get(eintrag)
        if calls is None:
            continue
        if not any(g in calls for g in (get_current_user, require_admin, require_atr_fair)):
            fehler.append(f"ANGEMELDET {eintrag[0]} ohne get_current_user")

    assert not fehler, "\n  - " + "\n  - ".join(sorted(fehler))


def test_keine_liste_enthaelt_eine_verschwundene_route():
    """Ein Eintrag ohne Route ist toter Ballast — und verdeckt beim nächsten
    gleichnamigen Pfad die Prüfung."""
    vorhanden = set()
    for route in _api_routen():
        vorhanden |= _eintraege(route)

    verwaist = sorted(
        f"{sorted(m)} {p}"
        for p, methoden in ADMIN_GATE_ALLOWLIST
        for m in [methoden]
        if not {(p, frozenset({x})) for x in methoden} & vorhanden
    )
    assert not verwaist, "gelistet, aber nicht registriert:\n  - " + "\n  - ".join(verwaist)


def test_die_listen_ueberschneiden_sich_nicht():
    """Eine Route gehört in genau eine Klasse."""
    assert not (OEFFENTLICH & GERAET)
    assert not (OEFFENTLICH & ANGEMELDET)
    assert not (GERAET & ANGEMELDET)
