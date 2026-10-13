"""Geländemodell für ein Gebiet an der Grenze von NRW und Niedersachsen.

Eine Abfrage, zwei Länder: geobasis fragt NRW (Ordnerverzeichnis) und
Niedersachsen (STAC-API) ab und legt alles in einen Ordner mit gemeinsamem
Manifest. Mit vrt=True entsteht ein Mosaik über die Landesgrenze hinweg.
"""

import geobasis

sel = geobasis.find("dgm1", bbox=(7.95, 52.15, 8.0, 52.19))  # Lienen (NRW) / Hagen a.T.W. (NI)
print(sel.summary())
res = sel.download("daten", vrt=True)
print(res.summary())
print("Mosaik:", res.vrt)
