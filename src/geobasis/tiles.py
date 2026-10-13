"""Parse tile coordinates from the file names used by the German state
survey offices.

NRW (like most AdV members) names tiles after their lower-left corner in
kilometres, e.g. ``dgm1_32_280_5652_1_nw_2022.tif`` = UTM zone 32,
E 280 km, N 5652 km, edge length 1 km, flown 2022. Variants seen in the
wild::

    dgm1_32_280_5652_1_nw_2022.tif      zone separated
    ndom50_32280_5652_1_nw_2023.tif     zone glued to the easting
    00_dgk5hls_32296_5640_2_nw.tif      prefix, 2 km tiles
    hoeae-s1_32_288_5664_16_EPSG25832_GeoPackage_2020-2024.gpkg
    dop40pan_2514_5612_2_nw_1951.jp2    Gauß-Krüger (zone digit + km)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_UTM = re.compile(r"(?:^|_)32_?(\d{3})_(\d{4})_(\d{1,2})(?=[_.]|$)")
_GK = re.compile(r"(?:^|_)([2-5])(\d{3})_(\d{4})_(\d{1,2})(?=[_.]|$)")
_YEAR = re.compile(r"_(?:[a-z]{2}|[A-Z]{2})_(\d{4})(?=[_.-]|$)")  # ..._nw_2022, ..._ni_2025-03-03


@dataclass(frozen=True)
class TileRef:
    """Grid position of a tile in metres (lower-left corner + edge length)."""

    crs: int
    x: float
    y: float
    size: float  # metres; 0 if unknown

    @property
    def key(self) -> str:
        return f"{int(self.x // 1000)}_{int(self.y // 1000)}"

    def bounds(self, default_size: float = 1000.0) -> tuple[float, float, float, float]:
        s = self.size or default_size
        return (self.x, self.y, self.x + s, self.y + s)


def parse_tile(name: str, crs: int | None = None) -> TileRef | None:
    """Return the grid reference encoded in ``name`` or ``None``.

    ``crs`` restricts parsing to UTM (25832) or a Gauß-Krüger code
    (31466/31467/...); by default UTM is tried first.
    """
    if crs in (None, 25832):
        m = _UTM.search(name)
        if m:
            return TileRef(25832, int(m.group(1)) * 1000.0, int(m.group(2)) * 1000.0,
                           int(m.group(3)) * 1000.0)
        if crs == 25832:
            return None
    m = _GK.search(name)
    if m:
        zone = int(m.group(1))
        code = 31464 + zone
        if crs not in (None, code):
            return None
        return TileRef(code, (zone * 1000 + int(m.group(2))) * 1000.0,
                       int(m.group(3)) * 1000.0, int(m.group(4)) * 1000.0)
    return None


def parse_year(name: str) -> int | None:
    m = _YEAR.search(name)
    return int(m.group(1)) if m else None
