# geobasis

**Amtliche Geodaten mit einer Zeile Python – zunächst für Nordrhein-Westfalen.**

> Inoffizielles Open-Source-Werkzeug. Kein Angebot der Vermessungsverwaltungen
> oder des Landes NRW; alle Daten kommen direkt von deren offiziellen Servern.

Die Vermessungsverwaltungen der Länder stellen Höhenmodelle, Luftbilder,
Kataster- und 3D-Gebäudedaten seit Jahren offen und kostenlos bereit. Genutzt
werden sie trotzdem wenig: Die Daten liegen in zehntausenden Kacheln mit
kryptischen Namen, verteilt über Portale, Ordnerbäume und OGC-Dienste. Wer
das Geländemodell für *eine* Gemeinde braucht, muss erst herausfinden, welche
der 35.860 Kacheln dazugehören.

`geobasis` nimmt diese Arbeit ab:

```bash
pip install geobasis
geobasis download dgm1 --gemeinde "Bad Honnef" -o daten
```

```python
from geobasis import nrw

auswahl = nrw.find("dop10", point=(6.958, 50.941), radius=500)   # Kölner Dom
print(auswahl.summary())
# dop10 (Digitale Orthophotos 10 cm (DOP10, RGBI)) für Punkt 6.958,50.941, Radius 500 m:
#   3 Datei(en), 72,0 MB, Stand 2025-05-11
auswahl.download("daten")
```

## Was es kann

- **32 Produkte aus NRW** mit stabilen Kurznamen: Gelände- und
  Oberflächenmodelle, Laserscanning-Punktwolken, Orthophotos (aktuell und
  73 Jahrgänge seit 1951), 3D-Gebäude, ALKIS, Karten, Landschaftsmodelle,
  Verwaltungsgrenzen. Vollständige Liste mit Größen: [docs/produkte.md](docs/produkte.md).
- **Gebiet statt Kachelnummer:** Gemeinde oder Kreis per Name oder Schlüssel,
  Punkt mit Radius, Rechteck in Grad oder UTM-Metern, beliebiges GeoJSON.
  Es werden nur Kacheln gewählt, die das Gebiet wirklich überlappen.
- **Aufnahmedatum je Kachel** aus den Metadaten-Beilagen von Geobasis NRW.
- **Flurstücke, Gebäude und Nutzung als Ausschnitt:** ALKIS-Objekte für ein
  beliebiges Polygon direkt als GeoPackage, ohne den ganzen Kreis zu laden.
- **Luftbild-Zeitreise:** `geobasis jahre dop-hist --punkt …` zeigt, aus
  welchen Jahren es für einen Ort Luftbilder gibt. Historische Kacheln in
  Gauß-Krüger werden automatisch richtig zugeordnet.
- **Robuste Downloads:** parallel, abgebrochene Dateien werden fortgesetzt,
  Größen werden geprüft, vorhandene Dateien übersprungen.
- **Nachvollziehbar:** Jeder Download schreibt eine `manifest.json` mit Quelle,
  Lizenz und Aufnahmedaten sowie eine `kacheln.geojson` für QGIS. Mit
  `--vrt` entsteht ein fertiges Raster-Mosaik (benötigt GDAL).
- **Keine Abhängigkeiten.** Reines Python ab Version 3.10, inklusive eigener
  Koordinatenumrechnung (UTM, Gauß-Krüger, Web-Mercator). Läuft damit auch
  dort, wo GDAL oder pyproj schwer zu installieren sind.

## Kommandozeile

```bash
geobasis produkte                                   # alle Produkte
geobasis info dop10                                 # Details, Dateizahl, Gesamtgröße
geobasis suche dgm1 --gemeinde Münster              # was würde geladen?
geobasis suche lod2 --kreis Kleve --umrisse k.geojson
geobasis download ndom50 --bbox 7.60,51.95,7.65,51.97 -o daten --vrt
geobasis download flurstuecke --punkt 7.626,51.962 --radius 300 -o daten
geobasis download alkis --kreis Warendorf -o daten --entpacken
geobasis jahre dop-hist --punkt 7.626,51.962        # Luftbild-Jahrgänge an einem Ort
geobasis download dop-hist --jahr 1954 --punkt 7.626,51.962 -o daten
geobasis gemeinden bad                              # Gemeinden suchen
geobasis dienste                                    # WMS/WFS-Adressen für QGIS
geobasis portal geobasis/lusat                      # Open-Data-Portal durchblättern
```

Gebiete: `--gemeinde`, `--kreis`, `--regbez` (Name oder amtlicher Schlüssel),
`--bbox`, `--punkt` mit `--radius` in Metern, `--geojson DATEI`. Koordinaten in
Grad werden als Länge,Breite gelesen; Werte in Metern als ETRS89/UTM32. Mit
`--crs` lässt sich das System festlegen. Downloads über 5 GB fragen nach, mit
`--ja` entfällt die Rückfrage, mit `--probelauf` wird nur angezeigt.

## Python

```python
from geobasis import nrw, Area

nrw.products()                           # Liste der Produkte
sel = nrw.find("dgm1", gemeinde="Münster")
sel.total_size, len(sel)                 # (632985401, 354)
sel[0].date, sel[0].bounds               # ('2024-01-20', (395000.0, 5755000.0, 396000.0, 5756000.0))
sel.save_geojson("kacheln.geojson")
res = sel.download("daten", workers=4, vrt=True)

# eigenes Gebiet
gebiet = Area.from_geojson("mein_gebiet.geojson")
nrw.find("lod2", area=gebiet).download("daten")

# Archive
nrw.product("dop-hist").years()
nrw.product("dop-hist").coverage(nrw.area(point=(7.626, 51.962)))
```

Mit `rasterio` lässt sich das Mosaik direkt weiterverarbeiten:
`rasterio.open(res.vrt).read(1)`.

## Datenlizenz

Alle Daten stammen von Geobasis NRW und stehen unter der
[Datenlizenz Deutschland – Zero – Version 2.0](https://www.govdata.de/dl-de/zero-2-0).
Sie dürfen ohne Einschränkung genutzt werden; ein Quellenvermerk
(„Land NRW (Jahr), dl-de/zero-2-0“) ist erwünscht.

## Wie es funktioniert

Das Open-Data-Portal von NRW ist ein Baum aus `index.json`-Dateien. `geobasis`
liest diese Verzeichnisse, entnimmt die Kachellage dem Dateinamen und prüft sie
gegen das gewünschte Gebiet. Gemeinde- und Kreisgrenzen kommen aus dem
WFS der Verwaltungsgrenzen, ALKIS-Ausschnitte aus dem ALKIS-WFS. Verzeichnisse
werden einen Tag zwischengespeichert (`geobasis cache`). Details stehen in
[docs/architektur.md](docs/architektur.md).

## Weitere Länder

Die Struktur ist auf alle 16 Länder ausgelegt: Ein Land ist eine Unterklasse
von `Land` mit eigenem Produktkatalog. Wie ein Land ergänzt wird, beschreibt
[docs/architektur.md](docs/architektur.md).

## Entwicklung

```bash
git clone https://github.com/Moerizzy/geobasis && cd geobasis
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                 # Offline-Tests gegen einen lokalen Nachbau des Portals
pytest -m online       # prüft alle Produkte gegen die echten Dienste
ruff check src tests
```

Beiträge sind willkommen, siehe [CONTRIBUTING.md](CONTRIBUTING.md).
Lizenz des Codes: [MIT](LICENSE).

---

### English summary

`geobasis` finds and downloads official open geodata of German states with
one line of Python. It currently covers North Rhine-Westphalia: 32 products
including 1 m terrain models, 10 cm orthophotos (plus a 1951–2024 archive),
LiDAR point clouds, LoD2 buildings and cadastre extracts. Select data by
municipality, district, point, bounding box or GeoJSON; downloads are
parallel, resumable and documented with a manifest. Pure Python, no
dependencies. Data: dl-de/zero-2-0. Code: MIT.
