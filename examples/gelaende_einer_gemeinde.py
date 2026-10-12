"""Geländemodell einer Gemeinde laden und als ein Mosaik bereitstellen."""

from geobasis import nrw

sel = nrw.find("dgm1", gemeinde="Bad Honnef")
print(sel.summary())
res = sel.download("daten", vrt=True)  # VRT braucht GDAL (gdalbuildvrt)
print(res.summary())
print("Mosaik:", res.vrt)
