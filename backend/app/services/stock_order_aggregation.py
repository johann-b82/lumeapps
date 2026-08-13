"""Bestellung auf Lager — Top-N Ladenhüter nach gebundenem Kapital (v1.106).

Business definition (agreed with the user):

* Basis sind die Lagerbewegungen (``material_movements`` / AswLagBew-Import),
  eingeschränkt auf **Lagerartikel** — Artikelnummer beginnt mit ``L``.
* **Menge** = aktueller Lagerbestand = ``SUM(bewegungsmenge)`` über *alle*
  geladenen Bewegungen des Artikels (Zugänge positiv, Entnahmen negativ).
* **Ladenhüter-Filter:** der Artikel hatte in den letzten ``inactive_days``
  Tagen (Default 28 = 4 Wochen) **gar keine Bewegung** — die jüngste
  Bewegung liegt also vor ``CURRENT_DATE - inactive_days`` — und der Bestand
  ist positiv.
* **Preis** = jüngster Einkaufs-Stückpreis des Artikels aus dem Wareneingang
  (``goods_receipt_records.price``), Join über die Artikelnummer.
* **Wert** = Bestand × Preis; absteigend sortiert, Top-N.

Compute-justified (CLAUDE.md clause 2): cross-table aggregation with a
DISTINCT-ON price pick — not expressible as a plain Directus collection read.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# One statement: net stock per L-article, kept only when its most recent
# movement is older than the inactivity window and the stock is positive,
# valued at the latest purchase unit price from the goods receipts.
_TOP_STOCK_ORDERS_SQL = text(
    """
    WITH bestand AS (
        SELECT artikelnr,
               MAX(article_name)   AS article_name,
               SUM(bewegungsmenge) AS stock_qty,
               MAX(buch_datum)     AS last_movement
        FROM material_movements
        WHERE artikelnr LIKE 'L%'
        GROUP BY artikelnr
    ),
    preis AS (
        SELECT DISTINCT ON (article_number) article_number, price
        FROM goods_receipt_records
        WHERE article_number LIKE 'L%' AND price IS NOT NULL
        ORDER BY article_number,
                 order_date   DESC NULLS LAST,
                 receipt_date DESC NULLS LAST
    )
    SELECT b.artikelnr                     AS article_number,
           b.article_name                  AS article_name,
           b.stock_qty                     AS stock_qty,
           p.price                         AS unit_price,
           (b.stock_qty * p.price)         AS value,
           b.last_movement                 AS last_movement
    FROM bestand b
    JOIN preis p ON p.article_number = b.artikelnr
    WHERE b.last_movement < :cutoff
      AND b.stock_qty > 0
    ORDER BY value DESC
    LIMIT :limit
    """
)


async def compute_top_stock_orders(
    db: AsyncSession,
    *,
    limit: int = 20,
    inactive_days: int = 28,
) -> list[dict[str, Any]]:
    """Return the Top-``limit`` slow-moving L-articles by tied-up capital.

    Each dict carries: ``rank``, ``article_number``, ``article_name``,
    ``stock_qty``, ``unit_price``, ``value``, ``last_movement``.
    """
    cutoff = date.today() - timedelta(days=inactive_days)
    result = await db.execute(
        _TOP_STOCK_ORDERS_SQL, {"cutoff": cutoff, "limit": limit}
    )
    rows = result.mappings().all()
    return [
        {
            "rank": i + 1,
            "article_number": r["article_number"],
            "article_name": r["article_name"],
            "stock_qty": float(r["stock_qty"]) if r["stock_qty"] is not None else 0.0,
            "unit_price": float(r["unit_price"]) if r["unit_price"] is not None else 0.0,
            "value": float(r["value"]) if r["value"] is not None else 0.0,
            "last_movement": r["last_movement"],
        }
        for i, r in enumerate(rows)
    ]
