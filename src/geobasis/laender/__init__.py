"""Registry of supported states. Currently: NRW."""

from __future__ import annotations

from .base import Land
from .nrw import nrw

LAENDER: dict[str, Land] = {"nw": nrw}
_ALIASES = {"nrw": "nw", "nordrhein-westfalen": "nw", "05": "nw"}


def land(code: str) -> Land:
    c = code.strip().lower()
    c = _ALIASES.get(c, c)
    if c not in LAENDER:
        raise KeyError(f"Land {code!r} wird (noch) nicht unterstützt. Verfügbar: "
                       f"{', '.join(sorted(LAENDER))}")
    return LAENDER[c]


__all__ = ["LAENDER", "Land", "land", "nrw"]
