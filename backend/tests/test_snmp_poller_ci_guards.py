"""CI guardrails for the SNMP poller — PITFALLS C-2, C-8 prevention + SEN-BE-14.

These tests are grep-style guards: they assert the absence of banned patterns
(sync DB drivers, time.sleep in async services, the deprecated pysnmp.hlapi.asyncio
import path) and the presence of required patterns (v3arch.asyncio import,
on_conflict_do_nothing, return_exceptions=True).

Running as unit tests means CI catches regressions the same way it would a
broken assertion — no separate shell script to maintain.
"""
import asyncio
import subprocess
from pathlib import Path

BACKEND_APP = Path(__file__).resolve().parents[1] / "app"
POLLER_PATH = BACKEND_APP / "services" / "snmp_poller.py"


def _grep(pattern: str, root: Path, extra_args: list[str] | None = None) -> list[str]:
    """Run grep -rnE (fails silently if no match). Returns matching lines."""
    cmd = ["grep", "-rnE", pattern, str(root)]
    if extra_args:
        cmd = ["grep", "-rnE", *extra_args, pattern, str(root)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return [l for l in result.stdout.splitlines() if l.strip()]


def test_no_sqlite3_or_psycopg2_imports():
    """SEN-BE-14 + PITFALLS C-2: async-only — no sync DB driver in backend/app/."""
    hits = _grep(r"^\s*(import (sqlite3|psycopg2)|from (sqlite3|psycopg2))", BACKEND_APP)
    # allow test files if any landed under backend/app mistakenly — filter below
    real_hits = [l for l in hits if "/tests/" not in l and "/__pycache__/" not in l]
    assert not real_hits, (
        f"Sync DB driver import found in backend/app/:\n" + "\n".join(real_hits)
    )


def test_no_time_sleep_in_snmp_services():
    """SEN-BE-14 + PITFALLS C-8: time.sleep blocks event loop — banned in SNMP services."""
    services = BACKEND_APP / "services"
    hits = []
    for f in services.glob("snmp*"):
        if f.is_file():
            out = subprocess.run(
                ["grep", "-nE", r"\btime\.sleep\b", str(f)],
                capture_output=True, text=True,
            )
            if out.stdout.strip():
                hits.extend(out.stdout.splitlines())
    assert not hits, f"time.sleep found in services/snmp*:\n" + "\n".join(hits)


def test_snmp_poller_uses_v3arch_import():
    """STACK.md: v7 idiom is v3arch.asyncio. Reference impl uses deprecated v1arch path."""
    text = POLLER_PATH.read_text()
    assert "from pysnmp.hlapi.v3arch.asyncio import" in text, (
        "snmp_poller.py must use the v3arch.asyncio import path (pysnmp 7.x idiom)."
    )
    assert "from pysnmp.hlapi.asyncio import" not in text, (
        "deprecated pysnmp.hlapi.asyncio (v6 path) found — use v3arch.asyncio."
    )


def test_snmp_poller_exports_expected_api():
    """SEN-BE-01: snmp_get, snmp_walk, poll_sensor, poll_all are public async functions."""
    from app.services import snmp_poller
    for name in ("snmp_get", "snmp_walk", "poll_sensor", "poll_all"):
        fn = getattr(snmp_poller, name, None)
        assert fn is not None, f"snmp_poller missing {name}"
        assert asyncio.iscoroutinefunction(fn), f"{name} must be async"


def test_snmp_poller_uses_on_conflict_do_nothing():
    """SEN-BE-11 / PITFALLS C-5: dedupe scheduled+manual poll collisions via ON CONFLICT."""
    text = POLLER_PATH.read_text()
    assert "on_conflict_do_nothing" in text, (
        "snmp_poller writes must use postgresql insert().on_conflict_do_nothing(...) "
        "with index_elements=['sensor_id','recorded_at'] to dedupe collisions."
    )


def test_snmp_poller_uses_return_exceptions():
    """SEN-BE-04 / PITFALLS M-3: gather default cancels siblings on one failure."""
    text = POLLER_PATH.read_text()
    # substring search (not regex) is fine — both `return_exceptions=True` and
    # `return_exceptions = True` on separate lines will match.
    assert "return_exceptions=True" in text or "return_exceptions = True" in text, (
        "poll_all must use asyncio.gather(..., return_exceptions=True) — one "
        "flaky sensor must not cancel sibling polls."
    )
