"""Sales-rep alias helpers.

The Kontakte file's ``Wer`` column is an uppercase surname token like
``KARRER`` or ``GUENDEL``. ``canonical_token`` derives the same shape
from a Personio employee's ``last_name`` so the Personio sync hook can
build a deterministic alias mapping table on every tick. Manual aliases
(``is_canonical = False``) handle nicknames the canonical rule does
not catch (e.g. ``GUENNI``).
"""
from __future__ import annotations

import re

_FOLDS = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "AE", "Ö": "OE", "Ü": "UE",
    "à": "a", "á": "a", "â": "a",
    "è": "e", "é": "e", "ê": "e",
})
_NON_ALPHA = re.compile(r"[^A-Z]")


def canonical_token(last_name: str | None) -> str:
    """Uppercased, umlaut-folded, alpha-only token.

    Empty string for ``None`` or empty input. Used both at sync time
    (deriving canonical alias rows from Personio) and as a hint for
    admin-supplied manual aliases (the create endpoint upper-cases the
    submitted token, but does not fold umlauts — admins type the token
    that actually appears in the Kontakte file).
    """
    if not last_name:
        return ""
    folded = last_name.translate(_FOLDS)
    return _NON_ALPHA.sub("", folded.upper())
