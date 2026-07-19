#!/usr/bin/python3
"""Set the ATR print-header (Doc-No / Date / Page + title, and the ACM logo)
via LibreOffice UNO, then export to PDF. Run with the distro python:
    /usr/bin/python3 atr_uno_header.py <in.xlsx> <out.pdf> <docno> <date> [logo.png]
"""
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue


def _pv(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def _connect(port, profile):
    proc = subprocess.Popen([
        "soffice", "--headless", "--invisible", "--nodefault", "--norestore",
        "--nologo", "--nofirststartwizard",
        f"-env:UserInstallation=file://{profile}",
        f"--accept=socket,host=127.0.0.1,port={port};urp;",
    ])
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(80):
        try:
            ctx = resolver.resolve(
                f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
            return proc, ctx
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("could not connect to soffice UNO socket")


def inject(in_path, out_path, docno, date_str, logo_path=None):
    port, profile = "2002", "/tmp/lo_uno_prof"
    proc, ctx = _connect(port, profile)
    try:
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(
            "file://" + in_path, "_blank", 0, (_pv("Hidden", True),))
        try:
            sheet = next((doc.Sheets.getByIndex(i) for i in range(doc.Sheets.Count)
                          if doc.Sheets.getByIndex(i).IsVisible), doc.Sheets.getByIndex(0))
            style = doc.StyleFamilies.getByName("PageStyles").getByName(sheet.PageStyle)
            style.HeaderIsOn = True
            hc = style.RightPageHeaderContent
            hc.CenterText.setString("ATR with WR and COC")
            rt = hc.RightText
            rt.setString(f"Doc-No.: {docno}\nDate: {date_str}\nPage: ")
            try:
                cur = rt.createTextCursor()
                cur.gotoEnd(False)
                pn = doc.createInstance("com.sun.star.text.TextField.PageNumber")
                pc = doc.createInstance("com.sun.star.text.TextField.PageCount")
                rt.insertTextContent(cur, pn, False)
                rt.insertString(cur, " of ", False)
                rt.insertTextContent(cur, pc, False)
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(f"page-field warning: {e}\n")
            if logo_path:
                try:
                    _set_header_logo(smgr, ctx, style, logo_path)
                except Exception as e:  # noqa: BLE001
                    sys.stderr.write(f"logo warning: {e}\n")
            style.RightPageHeaderContent = hc
            doc.storeToURL("file://" + out_path, (_pv("FilterName", "calc_pdf_Export"),))
        finally:
            doc.close(False)
        desktop.terminate()
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


def _set_header_logo(smgr, ctx, style, logo_path):
    """Place the logo top-left of the print header via the page style's header
    background graphic (LEFT_TOP).

    The other routes fail under LibreOffice's PDF export: the Excel '&G' header
    graphic (legacyDrawingHF/VML) is not rendered, a floating drawing shape gets
    clipped out of the header margin, and Calc headers can't hold a graphic via
    the text API (`createInstance('...TextGraphicObject')` returns None). The
    header background graphic renders and repeats on every page."""
    from com.sun.star.style.GraphicLocation import LEFT_TOP
    provider = smgr.createInstanceWithContext(
        "com.sun.star.graphic.GraphicProvider", ctx)
    graphic = provider.queryGraphic((_pv("URL", "file://" + logo_path),))
    style.setPropertyValue("HeaderBackGraphic", graphic)
    style.setPropertyValue("HeaderBackGraphicLocation", LEFT_TOP)
    try:
        style.setPropertyValue("HeaderHeight", 1400)  # ~14 mm — room for the logo
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    a = sys.argv
    inject(a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else None)
    print("uno header injected ->", a[2])
