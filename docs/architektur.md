# Architektur

## Überblick

```
src/geobasis/
  geo.py          Koordinaten (UTM, Gauß-Krüger, Web-Mercator), Shape, ShapeIndex
  area.py         Area: Gebiet aus Box, Punkt+Radius oder GeoJSON (immer EPSG:25832)
  tiles.py        Kachellage aus Dateinamen lesen
  models.py       Product, RemoteFile, Selection
  http.py         urllib mit Wiederholungen und Platten-Cache (ETag/Last-Modified)
  download.py     parallele, fortsetzbare Downloads, manifest.json, kacheln.geojson, VRT
  cli.py          Kommandozeile
  laender/
    base.py       Land: Katalog, Gebietsauflösung, find(), download()
    nrw/
      portal.py   Client für opengeodata.nrw.de (index.json, Metadaten-Beilagen)
      grenzen.py  Gemeinden/Kreise/Regierungsbezirke über den DVG-WFS
      wfs.py      ALKIS-Ausschnitte über den ALKIS-WFS (GeoPackage)
      products.py Produktklassen und der NRW-Katalog
      dienste.py  WMS/WFS-Adressen
```

## Ablauf einer Abfrage

1. **Gebiet auflösen.** `Land.area()` macht aus Gemeindename, Box, Punkt oder
   GeoJSON ein `Area`-Objekt. Gemeinden werden zuerst in der generalisierten
   DVG2-Liste gesucht (ein Abruf, 30 Tage zwischengespeichert), die genaue
   Grenze kommt dann gefiltert aus DVG1.
2. **Dateien auflisten.** Jedes Produkt kennt seinen Ordner im Portal. Die
   `index.json` liefert Dateinamen, Größen und Zeitstempel.
3. **Auswählen.**
   - *Kacheln:* Der Dateiname nennt die linke untere Ecke in km
     (`dgm1_32_280_5652_1_nw_2022.tif`). `ShapeIndex.intersects_rect` prüft,
     ob Kachel und Gebiet eine gemeinsame Fläche haben. Nur berührende Kacheln
     zählen nicht. Kanten des Gebiets liegen dafür in einem Gitterindex, die
     Innen-Prüfung nutzt zwischengespeicherte Scanlinien. Eine Gemeinde mit
     4.000 Stützpunkten gegen 36.000 Kacheln dauert so Millisekunden.
   - *Je Kreis/Regierungsbezirk:* Der amtliche Schlüssel steht im Dateinamen.
     Bei Gemeinden ergibt er sich direkt, sonst wird gegen die Kreisgrenzen
     geschnitten.
   - *WFS:* Das Gebiet geht als GML-Polygon in einen `Intersects`-Filter;
     vorher wird die Objektzahl abgefragt.
4. **Metadaten.** Liegt eine `*_meta.zip` bei, wird die CSV gelesen und jeder
   Kachel ihr Aufnahmedatum zugeordnet (über den Namen, sonst über die Lage).
5. **Herunterladen** in `ziel/<produkt>/`, mit Manifest und Umrissen.

## Historische Luftbilder

Bis 2009 liefert NRW Gauß-Krüger-Kacheln, und zwar für den Überlappungsstreifen
in beiden Zonen (EPSG:31466 und 31467). `geobasis` rechnet das Gebiet in die
jeweilige Zone um und wählt bei Doppelungen die Zone, deren Mittelmeridian
näher liegt. Die Datumsverschiebung DHDN→ETRS89 nutzt eine
7-Parameter-Helmert-Transformation, die auf etwa 2 m genau ist. Für die
Kachelwahl reicht das.

## Ein weiteres Land ergänzen

1. Ordner `laender/<kürzel>/` anlegen, eine Unterklasse von `Land` schreiben.
2. Produkte als Unterklassen von `Product` beschreiben und `_find()`
   implementieren. Für Kachelprodukte lässt sich `tiles.parse_tile` und
   `ShapeIndex` wiederverwenden; viele Länder benennen Kacheln nach demselben
   AdV-Schema.
3. `_admin_area()` für Gemeinden und Kreise implementieren, falls das Land
   einen Grenzen-Dienst anbietet. Alternativ kann der bundesweite VG250-Dienst
   des BKG dienen.
4. Das Land in `laender/__init__.py` registrieren.
5. Offline-Tests mit einem kleinen Nachbau der Dienste schreiben
   (Vorlage: `tests/fakeportal.py`) und einen Online-Test je Produkt.

## Tests

`pytest` startet einen lokalen HTTP-Server, der Portal-Ordner, Metadaten,
Range-Anfragen sowie DVG- und ALKIS-WFS nachbildet. Damit laufen alle Tests
ohne Netz in unter einer Sekunde. `pytest -m online` prüft jedes Produkt gegen
die echten Server; der CI-Lauf macht das wöchentlich, damit Änderungen am
Portal schnell auffallen.
