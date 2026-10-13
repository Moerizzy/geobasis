"""Registry of supported states."""

from __future__ import annotations

from .base import Land
from .ni import ni
from .nrw import nrw

LAENDER: dict[str, Land] = {"nw": nrw, "ni": ni}
_ALIASES = {"nrw": "nw", "nordrhein-westfalen": "nw", "05": "nw",
            "nds": "ni", "niedersachsen": "ni", "03": "ni"}


def land(code: str) -> Land:
    c = code.strip().lower()
    c = _ALIASES.get(c, c)
    if c not in LAENDER:
        raise KeyError(f"Land {code!r} wird (noch) nicht unterstützt. Verfügbar: "
                       f"{', '.join(sorted(LAENDER))}")
    return LAENDER[c]


__all__ = ["LAENDER", "Land", "land", "ni", "nrw"]
