"""Administrative units of NRW from the official DVG web service.

Names and rough extents come from the generalised DVG2 layer (one cached
request per level); the exact boundary of a selected unit is fetched from
the detailed DVG1 layer with a key filter. Both via
https://www.wfs.nrw.de/geobasis/wfs_nw_dvg (dl-de/zero-2-0).
"""

from __future__ import annotations

import urllib.parse

from ... import http
from ...geo import Shape
from ...grenzen import BoundaryProvider, Unit, bbox_of_geometry

WFS = "https://www.wfs.nrw.de/geobasis/wfs_nw_dvg"
LAYERS = {"gemeinde": "gem", "kreis": "krs", "regbez": "rbz"}
_TTL = 30 * 24 * 3600  # boundaries change rarely


def _url(typename: str, flt: str | None = None) -> str:
    q = {"SERVICE": "WFS", "REQUEST": "GetFeature", "VERSION": "2.0.0",
         "TYPENAMES": f"dvg:{typename}", "OUTPUTFORMAT": "application/json; subtype=geojson"}
    if flt:
        q["FILTER"] = flt
    return WFS + "?" + urllib.parse.urlencode(q)


class DvgProvider(BoundaryProvider):
    land = "nw"
    levels = ("gemeinde", "kreis", "regbez")

    def _fetch_units(self, level: str) -> list[Unit]:
        d = http.fetch_json(_url(f"nw_dvg2_{LAYERS[level]}"), ttl=_TTL)
        return [Unit(level, f["properties"]["KN"], f["properties"]["GN"],
                     bbox_of_geometry(f["geometry"]), land=self.land)
                for f in d.get("features") or [] if f.get("geometry")]

    def _fetch_geometry(self, level: str, ags: str) -> Shape:
        flt = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo>'
               f"<fes:ValueReference>KN</fes:ValueReference><fes:Literal>{ags}</fes:Literal>"
               "</fes:PropertyIsEqualTo></fes:Filter>")
        d = http.fetch_json(_url(f"nw_dvg1_{LAYERS[level]}", flt), ttl=_TTL)
        if not d.get("features"):
            raise LookupError(f"Keine Geometrie für {ags} ({level}) gefunden")
        return Shape.from_geojson(d, crs=25832)


provider = DvgProvider()
