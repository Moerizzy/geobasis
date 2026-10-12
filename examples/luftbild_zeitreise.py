"""Welche historischen Luftbilder gibt es für einen Ort? Ältestes und neuestes laden."""

from geobasis import nrw

gebiet = nrw.area(point=(7.6261, 51.9625))  # Prinzipalmarkt Münster
archiv = nrw.product("dop-hist")
jahre = [j for j, n in archiv.coverage(gebiet).items() if n]
print("Luftbilder aus:", ", ".join(map(str, jahre)))
for jahr in (jahre[0], jahre[-1]):
    sel = archiv.find(gebiet, year=jahr)
    print(jahr, sel.summary())
    sel.download("daten")
