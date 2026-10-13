"""Queries across states: one call, data from every state the area touches.

>>> import geobasis
>>> sel = geobasis.find("dgm1", bbox=(7.9, 52.2, 8.1, 52.4))   # NRW + Niedersachsen
>>> sel.summary()
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .area import Area
from .laender import LAENDER, Land, land
from .models import Selection

if TYPE_CHECKING:  # pragma: no cover
    from .download import DownloadResult

_LEVELS = ("gemeinde", "kreis", "regbez")


def _lands(code: str | None) -> list[Land]:
    return [land(code)] if code else list(LAENDER.values())


def area(*, land: str | None = None, **kw) -> tuple[Area | None, list[Land]]:
    """Resolve an area and the states it belongs to.

    Municipalities and districts are searched in every state (or only in
    ``land``); a name that exists in several states must be disambiguated.
    Geometric areas (bbox, point, GeoJSON) are routed to every state whose
    extent they touch."""
    lands = _lands(land)
    admin = [(lv, kw[lv]) for lv in _LEVELS if kw.get(lv) is not None]
    others = [k for k in ("area", "bbox", "point", "geojson") if kw.get(k) is not None]
    if len(admin) + len(others) > 1:
        raise ValueError(f"Bitte nur eine Gebietsangabe verwenden, nicht "
                         f"{', '.join([lv for lv, _ in admin] + others)}")
    if admin:
        level, query = admin[0]
        digits = re.sub(r"\s", "", str(query))
        if digits.isdigit() and len(digits) >= 2:  # the AGS names its state
            lands = [lnd for lnd in lands if lnd.ags == digits[:2]] or lands
        hits, errors = [], []
        for lnd in lands:
            if lnd.boundaries is None or level not in lnd.boundaries.levels:
                continue
            try:
                unit, rank = lnd.boundaries.lookup_ranked(level, query)
                hits.append((rank, lnd, unit))
            except LookupError as e:
                if "mehrdeutig" in str(e):
                    raise
                errors.append(str(e))
        if hits:  # an exact match in one state beats a loose one in another
            best = min(r for r, _, _ in hits)
            hits = [(lnd, u) for r, lnd, u in hits if r == best]
        if len(hits) == 1:
            lnd, unit = hits[0]
            return lnd.boundaries.area_of(unit), [lnd]
        if len(hits) > 1:
            opts = ", ".join(f"{u.label} in {lnd.name}" for lnd, u in hits)
            raise LookupError(f"{query!r} gibt es in mehreren Ländern: {opts}. "
                              "Bitte --land angeben oder den Schlüssel verwenden.")
        raise LookupError(" ".join(dict.fromkeys(errors)) or
                          f"Keine Verwaltungseinheit {query!r} gefunden.")
    if not others:
        return None, lands
    first = lands[0]
    a = first.area(**{k: v for k, v in kw.items() if k not in _LEVELS})
    touched = [lnd for lnd in lands if lnd.bbox is None or lnd.bbox.intersects(a.shape.bbox)]
    return a, touched


def find(product: str, *, land: str | None = None, year: int | None = None,
         variant: str | None = None, latest: bool = True, with_meta: bool = True,
         **area_kw) -> Selection:
    """Files of ``product`` for an area across all states it touches."""
    a, lands = area(land=land, **area_kw)
    with_product = [lnd for lnd in lands if lnd.has_product(product)]
    if not with_product:
        names = sorted({n for lnd in lands for p in lnd.products() for n in (p.id, *p.aliases)})
        close = difflib.get_close_matches(product.lower(), names, n=4, cutoff=0.5)
        hint = f" Meinten Sie: {', '.join(close)}?" if close else ""
        where = " oder ".join(lnd.short for lnd in lands)
        raise KeyError(f"Produkt {product!r} gibt es für {where} nicht.{hint} "
                       "Alle Produkte: geobasis produkte")
    parts: list[Selection] = []
    for lnd in with_product:
        p = lnd.product(product)
        parts.append(p.find(a, year=year, variant=variant if variant in p.variants else None,
                            latest=latest, with_meta=with_meta))
    with_files = [s for s in parts if s]
    parts = with_files or parts[:1]  # states without hits only add noise
    if len(parts) == 1:
        return parts[0]
    files = [f for s in parts for f in s]
    notes = [f"{s.product.land.upper()}: {n}" for s in parts for n in s.notes]
    return Selection(files, parts[0].product, a, notes, products=[s.product for s in parts],
                     name=product.lower())


def download(product: str, out: str | Path = ".", *, land: str | None = None,
             year: int | None = None, variant: str | None = None, latest: bool = True,
             workers: int = 4, overwrite: bool = False, progress: bool = True,
             vrt: bool = False, extract: bool = False, **area_kw) -> DownloadResult:
    sel = find(product, land=land, year=year, variant=variant, latest=latest, **area_kw)
    return sel.download(out, workers=workers, overwrite=overwrite, progress=progress, vrt=vrt,
                        extract=extract)
