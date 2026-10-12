"""Flurstücke und Gebäude rund um einen Punkt als GeoPackage."""

from geobasis import nrw

ort = dict(point=(7.6261, 51.9625), radius=300)  # Prinzipalmarkt Münster
for produkt in ("flurstuecke", "gebaeude"):
    sel = nrw.find(produkt, **ort)
    print(sel.summary(), *sel.notes)
    print(sel.download("daten").files)
