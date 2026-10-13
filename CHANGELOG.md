# Änderungen

## 0.2.0 – 2026-10-12

- Niedersachsen als zweites Land: DGM1, DOM1, bDOM20, DOP20 (RGB oder RGBI),
  DOP10 und das Luftbildarchiv seit 2012, gelesen über die STAC-APIs des LGLN.
- Länderübergreifende Suche: `geobasis.find(...)` und die Kommandozeile fragen
  alle Länder ab, die das Gebiet berührt, und führen die Ergebnisse zusammen.
- Gemeinden und Kreise in Niedersachsen über VG250/VG25 des BKG; mehrdeutige
  Namen (Stadt/Landkreis, gleichnamige Gemeinden) werden mit Kreis angezeigt.
- Manifest mit Quelle, Lizenz und Namensnennung je Land.
- `--land` funktioniert vor und nach dem Befehl.

## 0.1.0 – 2026-10-12

Erster Prototyp.

- 32 Produkte für Nordrhein-Westfalen (Höhenmodelle, Luftbilder inkl. Archiv
  seit 1951, 3D-Gebäude, ALKIS, Karten, Landschaftsmodelle, Verwaltungsgrenzen).
- Gebietsauswahl über Gemeinde, Kreis, Regierungsbezirk, Box, Punkt mit Radius, GeoJSON.
- ALKIS-Ausschnitte als GeoPackage über den WFS.
- Aufnahmedatum je Kachel aus den Metadaten-Beilagen.
- Parallele, fortsetzbare Downloads mit Manifest, Kachelumrissen und optionalem VRT.
- Kommandozeile `geobasis` und Python-API, ohne externe Abhängigkeiten.
