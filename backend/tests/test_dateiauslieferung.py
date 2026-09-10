"""Befund 13, 14, 15: wie gespeicherte Dateien das Haus verlassen."""
from __future__ import annotations

import pytest

from app.security.dateien import INLINE_ERLAUBT, auslieferung, sicherer_dateiname


# --- Dateinamen (Befund 15) --------------------------------------------------


@pytest.mark.parametrize(
    "roh, erwartet",
    [
        ("Bericht 2026.pdf", "Bericht 2026.pdf"),
        ('a"; rm -rf /.pdf', "a__ rm -rf _.pdf"),
        # Führende Punkte fallen weg — sonst entstünden Namen wie ".htaccess".
        ("../../etc/passwd", "_.._etc_passwd"),
        ("zeile\r\nX-Injected: 1", "zeile__X-Injected_ 1"),
        ("Prüfbericht.pdf", "Pr_fbericht.pdf"),
        ("", "datei"),
        (None, "datei"),
        ("...", "datei"),
    ],
)
def test_sicherer_dateiname(roh, erwartet):
    assert sicherer_dateiname(roh) == erwartet


def test_umlaute_kommen_ueber_filename_stern_mit():
    _, kopf = auslieferung("Prüfbericht.pdf", "application/pdf")
    disposition = kopf["Content-Disposition"]
    assert 'filename="Pr_fbericht.pdf"' in disposition
    assert "filename*=UTF-8''Pr%C3%BCfbericht.pdf" in disposition


def test_kein_umbruch_gelangt_in_die_kopfzeile():
    _, kopf = auslieferung("a\r\nSet-Cookie: b", "application/pdf")
    assert "\r" not in kopf["Content-Disposition"]
    assert "\n" not in kopf["Content-Disposition"]


# --- Auslieferung (Befund 13) ------------------------------------------------


@pytest.mark.parametrize("typ", sorted(INLINE_ERLAUBT))
def test_harmlose_typen_bleiben_inline_und_behalten_ihren_typ(typ):
    media_type, kopf = auslieferung("datei.bin", typ)
    assert media_type == typ
    assert kopf["Content-Disposition"].startswith("inline;")
    assert kopf["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize(
    "typ",
    ["text/html", "image/svg+xml", "application/xhtml+xml", "text/xml", "", None],
)
def test_ausfuehrbare_typen_gehen_in_den_anhang(typ):
    """HTML und SVG laufen sonst im Ursprung der Anwendung."""
    media_type, kopf = auslieferung("boese.html", typ)
    assert media_type == "application/octet-stream"
    assert kopf["Content-Disposition"].startswith("attachment;")
    assert kopf["X-Content-Type-Options"] == "nosniff"


def test_inline_false_erzwingt_den_anhang_auch_fuer_pdf():
    media_type, kopf = auslieferung("bericht.pdf", "application/pdf", inline=False)
    assert media_type == "application/pdf"
    assert kopf["Content-Disposition"].startswith("attachment;")


def test_image_jpg_gilt_als_jpeg():
    """Kein echter MIME-Typ, aber verbreitet — sonst fiele das Bild in den Anhang."""
    media_type, kopf = auslieferung("foto.jpg", "image/jpg")
    assert media_type == "image/jpeg"
    assert kopf["Content-Disposition"].startswith("inline;")


def test_parameter_am_typ_stoeren_nicht():
    media_type, _ = auslieferung("a.pdf", "application/pdf; charset=binary")
    assert media_type == "application/pdf"


def test_svg_ist_bewusst_nicht_erlaubt():
    assert "image/svg+xml" not in INLINE_ERLAUBT


# --- Am echten Weg nachgeprüft ----------------------------------------------


@pytest.mark.asyncio
async def test_newsletter_bild_mit_falschem_typ_geht_in_den_anhang(viewer_client):
    """Der MIME-Typ eines Eintragsbilds kommt vom Hochladenden.

    Wer ihn auf ``text/html`` setzt, bekam die Datei bisher inline im
    Ursprung der Anwendung zurück — mit Zugriff auf die Sitzung jedes
    Betrachters. Der Weg ist hier vollständig durchgespielt, nicht nur
    der Helfer.
    """
    from datetime import datetime, timezone

    from sqlalchemy import delete

    from app.database import AsyncSessionLocal
    from app.models.newsletter import Newsletter, NewsletterEintrag

    jetzt = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as s:
        ausgabe = Newsletter(
            jahr=2099, quartal=4, titel="Testausgabe",
            erstellt_am=jetzt, aktualisiert_am=jetzt,
        )
        s.add(ausgabe)
        await s.commit()
        await s.refresh(ausgabe)
        eintrag = NewsletterEintrag(
            newsletter_id=ausgabe.id,
            rubrik="intern",
            untertitel="Boesartig",
            inhalt_md="",
            bild_data=b"<script>alert(document.cookie)</script>",
            bild_mime="text/html",
        )
        s.add(eintrag)
        await s.commit()
        await s.refresh(eintrag)
        eintrag_id, ausgabe_id = eintrag.id, ausgabe.id

    try:
        r = await viewer_client.get(f"/api/newsletter/eintrag/{eintrag_id}/bild")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/octet-stream")
        assert r.headers["content-disposition"].startswith("attachment;")
        assert r.headers["x-content-type-options"] == "nosniff"
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(
                delete(NewsletterEintrag).where(NewsletterEintrag.id == eintrag_id)
            )
            await s.execute(delete(Newsletter).where(Newsletter.id == ausgabe_id))
            await s.commit()
