"""Canonical KPI registry for the KPI-Bewertung/Maßnahmen module (v1.107).

Stable identifiers that KPI comments and measures anchor to, so a comment
survives dashboard refactors. The frontend maps ``key`` → an i18n label; the
backend only owns the key + its domain (used to group the hub view and to
validate that a comment/measure references a known KPI).

Add a new KPI card ⇒ add its key here (single source of truth).
"""
from __future__ import annotations

# (domain, key) — domain groups the hub; key is the stable anchor.
KPI_REGISTRY: list[dict[str, str]] = [
    {"domain": "sales", "key": "sales.revenue"},
    {"domain": "sales", "key": "sales.erstkontakte"},
    {"domain": "sales", "key": "sales.interessenten"},
    {"domain": "sales", "key": "sales.besuche"},
    {"domain": "sales", "key": "sales.angebote"},
    {"domain": "sales", "key": "sales.orders_per_rep"},
    {"domain": "hr", "key": "hr.overtime_ratio"},
    {"domain": "hr", "key": "hr.sick_leave_ratio"},
    {"domain": "hr", "key": "hr.fluctuation"},
    {"domain": "hr", "key": "hr.revenue_per_employee"},
    {"domain": "quality", "key": "quality.complaint_customer"},
    {"domain": "quality", "key": "quality.complaint_internal"},
    {"domain": "quality", "key": "quality.complaint_supplier"},
    {"domain": "quality", "key": "quality.complaint_subcontractor"},
    {"domain": "quality", "key": "quality.audit_findings"},
    {"domain": "quality", "key": "quality.inspections"},
    {"domain": "finance", "key": "finance.material_cost_ratio"},
    {"domain": "finance", "key": "finance.personnel_cost_ratio"},
    {"domain": "procurement", "key": "procurement.otd"},
    {"domain": "procurement", "key": "procurement.stock_orders"},
    {"domain": "production", "key": "production.verzug"},
]

KPI_KEYS: frozenset[str] = frozenset(item["key"] for item in KPI_REGISTRY)


def is_known_kpi(key: str) -> bool:
    return key in KPI_KEYS
