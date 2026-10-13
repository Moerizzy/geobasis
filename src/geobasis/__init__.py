"""geobasis – amtliche Geobasisdaten mit einer Zeile Python.

>>> import geobasis
>>> sel = geobasis.find("dgm1", gemeinde="Bad Honnef")
>>> print(sel.summary())
>>> sel.download("daten/")

Einzelne Länder: ``geobasis.nrw``, ``geobasis.ni``.
"""

from __future__ import annotations

from ._version import __version__
from .area import Area
from .bund import area, download, find
from .download import DownloadResult
from .laender import LAENDER, Land, land, ni, nrw
from .models import Product, RemoteFile, Selection

__all__ = ["LAENDER", "Area", "DownloadResult", "Land", "Product", "RemoteFile", "Selection",
           "__version__", "area", "download", "find", "land", "ni", "nrw", "products"]


def products() -> list[Product]:
    """All products of all supported states."""
    return [p for lnd in LAENDER.values() for p in lnd.products()]
