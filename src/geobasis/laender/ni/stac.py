"""Minimal client for the STAC APIs of the LGLN (Niedersachsen).

Each product family has its own STAC API (OGC API - Features) with a
server-side ``bbox`` and ``datetime`` search; results are paged with
``next`` links. Item geometries are in WGS84, assets are Cloud-Optimized
GeoTIFFs on object storage.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Iterator

from ... import http

ENDPOINTS = {
    "dgm": "https://dgm.stac.lgln.niedersachsen.de",
    "dom": "https://dom.stac.lgln.niedersachsen.de",
    "bdom": "https://bdom.stac.lgln.niedersachsen.de",
    "dop": "https://dop.stac.lgln.niedersachsen.de",
}
PAGE = 1000


def collection(service: str, coll: str) -> dict:
    return http.fetch_json(f"{ENDPOINTS[service].rstrip('/')}/collections/{coll}")


def items(service: str, coll: str, bbox: tuple[float, float, float, float] | None = None,
          datetime: str | None = None, limit: int | None = None) -> Iterator[dict]:
    """All items of a collection, optionally restricted to a WGS84 bbox and a
    datetime interval like ``2020-01-01T00:00:00Z/2020-12-31T23:59:59Z``."""
    params: dict[str, str] = {"limit": str(limit or PAGE)}
    if bbox:
        params["bbox"] = ",".join(f"{v:.7f}" for v in bbox)
    if datetime:
        params["datetime"] = datetime
    url: str | None = (f"{ENDPOINTS[service].rstrip('/')}/collections/{coll}/items?"
                       + urllib.parse.urlencode(params))
    seen: set[str] = set()
    while url and url not in seen:
        seen.add(url)
        page = http.fetch_json(url)
        yield from page.get("features") or []
        url = next((link["href"] for link in page.get("links") or [] if link.get("rel") == "next"),
                   None)
