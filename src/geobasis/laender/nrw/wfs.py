"""Area extracts from the ALKIS (simplified schema) WFS of NRW.

The service https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht
returns GeoPackages directly and supports spatial filters, so parcels,
buildings or land use for an arbitrary polygon arrive in one request -
no need to download the full district archive.
"""

from __future__ import annotations

import re

from ... import http
from ...geo import Shape

ALKIS_WFS = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
NS_AVE = "http://repository.gdi-de.org/schemas/adv/produkt/alkis-vereinfacht/2.0"
GPKG = "application/geopackage+sqlite3"


def _poslist(ring) -> str:
    return " ".join(f"{x:.3f} {y:.3f}" for x, y in ring)


def gml_geometry(shape: Shape) -> str:
    """GML 3.2 (multi)surface for the shape in EPSG:25832.

    Every ring becomes its own polygon (holes are filled), which can only
    return *more* objects, never fewer. Line/point shapes use their bbox."""
    srs = 'srsName="urn:ogc:def:crs:EPSG::25832"'
    rings = list(shape.rings)
    if not rings:
        b = shape.bbox.buffer(0.5)
        rings = [[(b.minx, b.miny), (b.maxx, b.miny), (b.maxx, b.maxy), (b.minx, b.maxy),
                  (b.minx, b.miny)]]
    polys = []
    for i, r in enumerate(rings):
        polys.append(f'<gml:Polygon gml:id="p{i}" {srs}><gml:exterior><gml:LinearRing>'
                     f"<gml:posList>{_poslist(r)}</gml:posList></gml:LinearRing></gml:exterior>"
                     "</gml:Polygon>")
    if len(polys) == 1:
        return polys[0]
    members = "".join(f"<gml:surfaceMember>{p}</gml:surfaceMember>" for p in polys)
    return f'<gml:MultiSurface gml:id="aoi" {srs}>{members}</gml:MultiSurface>'


def getfeature_body(typename: str, shape: Shape, *, hits: bool = False,
                    output_format: str = GPKG) -> bytes:
    rt = ' resultType="hits"' if hits else ""
    fmt = "" if hits else f' outputFormat="{output_format}"'
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<wfs:GetFeature service="WFS" version="2.0.0"{rt}{fmt} '
        'xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:fes="http://www.opengis.net/fes/2.0" '
        f'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:ave="{NS_AVE}">'
        f'<wfs:Query typeNames="{typename}"><fes:Filter><fes:Intersects>'
        f"<fes:ValueReference>ave:geometrie</fes:ValueReference>{gml_geometry(shape)}"
        "</fes:Intersects></fes:Filter></wfs:Query></wfs:GetFeature>"
    )
    return xml.encode("utf-8")


def count(typename: str, shape: Shape) -> int:
    """Number of objects of ``typename`` touching the shape."""
    with http.request(ALKIS_WFS, data=getfeature_body(typename, shape, hits=True),
                      headers={"Content-Type": "application/xml"}) as r:
        text = r.read(65536).decode("utf-8", "replace")
    m = re.search(r'numberMatched="(\d+)"', text)
    if not m:
        raise http.HTTPError(ALKIS_WFS, f"Unerwartete WFS-Antwort: {text[:300]}")
    return int(m.group(1))
