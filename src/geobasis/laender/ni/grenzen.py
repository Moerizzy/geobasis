"""Municipalities and districts of Niedersachsen from the BKG boundary services.

The list of units comes from VG250 (one cached request per level, filtered
to Niedersachsen); the boundary of a selected unit from the more detailed
VG25 (scale 1:25 000). Source: © GeoBasis-DE / BKG, dl-de/by-2-0.
"""

from __future__ import annotations

import urllib.parse

from ... import http
from ...geo import Shape
from ...grenzen import BoundaryProvider, Unit, bbox_of_geometry

VG250_WFS = "https://sgx.geodatenzentrum.de/wfs_vg250"
VG25_WFS = "https://sgx.geodatenzentrum.de/wfs_vg25"
LAYERS = {"gemeinde": "gem", "kreis": "krs"}
_TTL = 30 * 24 * 3600


def _filter(field: str, value: str) -> str:
    return ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo>'
            f"<fes:ValueReference>{field}</fes:ValueReference><fes:Literal>{value}</fes:Literal>"
            "</fes:PropertyIsEqualTo></fes:Filter>")


def _url(base: str, typename: str, flt: str) -> str:
    q = {"SERVICE": "WFS", "REQUEST": "GetFeature", "VERSION": "2.0.0", "TYPENAMES": typename,
         "OUTPUTFORMAT": "application/json", "SRSNAME": "urn:ogc:def:crs:EPSG::25832",
         "FILTER": flt}
    return base + "?" + urllib.parse.urlencode(q)


class Vg25Provider(BoundaryProvider):
    land = "ni"
    land_key = "03"
    levels = ("gemeinde", "kreis")

    def _fetch_units(self, level: str) -> list[Unit]:
        layer = f"vg250:vg250_{LAYERS[level]}"
        d = http.fetch_json(_url(VG250_WFS, layer, _filter("sn_l", self.land_key)), ttl=_TTL)
        merged: dict[str, Unit] = {}
        for f in d.get("features") or []:
            p, g = f.get("properties") or {}, f.get("geometry")
            if not g:
                continue
            ags, bb = p["ags"].ljust(8, "0"), bbox_of_geometry(g)  # Kreise: 5 digits
            old = merged.get(ags)
            if old:  # coastal units come as land and water parts
                bb = type(bb)(min(bb.minx, old.bbox.minx), min(bb.miny, old.bbox.miny),
                              max(bb.maxx, old.bbox.maxx), max(bb.maxy, old.bbox.maxy))
            merged[ags] = Unit(level, ags, p["gen"], bb, bez=p.get("bez") or "", land=self.land)
        return list(merged.values())

    def _fetch_geometry(self, level: str, ags: str) -> Shape:
        key = ags[:5] if level == "kreis" else ags
        d = http.fetch_json(_url(VG25_WFS, f"vg25:vg25_{LAYERS[level]}", _filter("ags", key)),
                            ttl=_TTL)
        if not d.get("features"):
            raise LookupError(f"Keine Geometrie für {ags} ({level}) gefunden")
        return Shape.from_geojson(d, crs=25832)


provider = Vg25Provider()
