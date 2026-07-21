"""CLI: import the internal audit programme workbook into the Audit-Modul.

    python scripts/import_audit_programme.py <xlsx> [--commit] [--actor <uuid>]

Runs as a dry-run by default: it parses, writes everything inside a transaction,
prints the report and rolls back. Pass --commit to keep the changes.
"""
import argparse
import asyncio
import sys
import uuid

sys.path.insert(0, "/app")

from app.database import AsyncSessionLocal  # noqa: E402
from app.schemas import CurrentUser  # noqa: E402
from app.security.roles import Role  # noqa: E402
from app.services.audit_import_programme import (  # noqa: E402
    import_programme,
    parse_programme,
)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook")
    ap.add_argument("--commit", action="store_true", help="persist (default: dry-run)")
    ap.add_argument(
        "--actor",
        default="11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        help="Directus user UUID recorded as the actor in the audit trail",
    )
    args = ap.parse_args()

    parsed, warnings = parse_programme(args.workbook)
    print(f"Geparst: {len(parsed)} Audits, {len(warnings)} Warnung(en)\n")
    for a in parsed:
        print(f"  {a.audit_number:<14} {a.planned_start} {'+'.join(a.categories):<16} "
              f"{(a.lead_auditor or '-'):<10} {len(a.norm_clauses):>3} Klauseln  {a.title[:38]}")
    if warnings:
        print("\nWarnungen:")
        for w in warnings:
            print("  ! " + w)

    actor = CurrentUser(
        id=uuid.UUID(args.actor),
        email=f"{args.actor}@directus.example.com",
        role=Role.ADMIN,
    )

    async with AsyncSessionLocal() as session:
        report = await import_programme(
            session, actor, parsed, warnings, dry_run=not args.commit
        )

    mode = "COMMIT" if args.commit else "DRY-RUN (zurückgerollt)"
    print(f"\n=== {mode} ===")
    print(f"  Audits angelegt:      {len(report.audits_created)}")
    print(f"  Audits übersprungen:  {len(report.audits_skipped)} {report.audits_skipped or ''}")
    print(f"  Normzeilen neu:       {len(report.norms_created)}")
    print(f"  Normzeilen wiederverwendet: {report.norms_reused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
