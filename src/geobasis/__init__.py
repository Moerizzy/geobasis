"""geobasis – amtliche Geobasisdaten mit einer Zeile Python.

>>> from geobasis import nrw
>>> sel = nrw.find("dgm1", gemeinde="Bad Honnef")
>>> print(sel.summary())
>>> sel.download("daten/")
"""

from __future__ import annotations

from ._version import __version__
from .area import Area
from .download import DownloadResult
from .laender import LAENDER, Land, land, nrw
from .models import Product, RemoteFile, Selection

__all__ = ["LAENDER", "Area", "DownloadResult", "Land", "Product", "RemoteFile", "Selection",
           "__version__", "land", "nrw", "products"]


def products() -> list[Product]:
    """All products of all supported states."""
    return [p for lnd in LAENDER.values() for p in lnd.products()]
