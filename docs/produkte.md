# Produkte

Stand der Zahlen: 12.10.2026, erzeugt mit `python scripts/produkttabelle.py`. Wo „–“ steht, fragt geobasis den Katalog gezielt für das gewünschte Gebiet ab, statt ihn ganz aufzulisten.

# Nordrhein-Westfalen

Lizenz: Datenlizenz Deutschland – Zero – Version 2.0 (dl-de/zero-2-0). Namensnennung: „Land NRW (Jahr), Datenlizenz Deutschland – Zero – Version 2.0“.

## Höhenmodelle

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `dgm1` | Digitales Geländemodell 1 m (DGM1) | Kacheln | GeoTIFF | 35.860 | 78,8 GB |
| `dom1` | Digitales Oberflächenmodell 1 m (DOM1) | Kacheln | GeoTIFF | 35.860 | 85,1 GB |
| `ndom50` | Normalisiertes Oberflächenmodell 50 cm (nDOM50) | Kacheln | GeoTIFF | 35.860 | 574,7 GB |
| `bdom50` | Bildbasiertes Oberflächenmodell 50 cm (bDOM50) | Kacheln | LAZ (Punktwolke) | 35.860 | 511,6 GB |
| `laserscan` | 3D-Messdaten Laserscanning (Punktwolke) | Kacheln | LAZ (Punktwolke) | 35.860 | 3,5 TB |

## Luftbilder

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `dop10` | Digitale Orthophotos 10 cm (DOP10, RGBI) | Kacheln | JPEG 2000 | 35.860 | 1,2 TB |
| `idop20` | InVeKoS-Orthophotos 20 cm (iDOP20, RGBI) | Kacheln | JPEG 2000 | 32.924 | 1,6 TB |
| `dop-hist` | Historische Orthophotos (Luftbildarchiv seit 1951) | Kacheln | JPEG 2000 | 73 Jahrgänge (1951–2024) | – |
| `landbedeckung` | Landbedeckung NRW (GeoPackage) | je Kreis/Bezirk | GeoPackage (ZIP) | 5 | 4,5 GB |

## 3D-Gebäude

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `lod2` | 3D-Gebäudemodell LoD2 (CityGML) | Kacheln | CityGML | 35.022 | 219,6 GB |
| `lod1` | 3D-Gebäudemodell LoD1 (CityGML) | Kacheln | CityGML | 35.022 | 91,8 GB |

## Liegenschaftskataster

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `flurstuecke` | Flurstücke (ALKIS, Ausschnitt per WFS) | Ausschnitt (WFS) | GeoPackage | – | je nach Gebiet |
| `gebaeude` | Gebäude (ALKIS, Ausschnitt per WFS) | Ausschnitt (WFS) | GeoPackage | – | je nach Gebiet |
| `nutzung` | Tatsächliche Nutzung (ALKIS, Ausschnitt per WFS) | Ausschnitt (WFS) | GeoPackage | – | je nach Gebiet |
| `katasterbezirke` | Gemarkungen und Fluren (ALKIS, per WFS) | Ausschnitt (WFS) | GeoPackage | – | je nach Gebiet |
| `verwaltungseinheiten` | Verwaltungseinheiten (ALKIS, per WFS) | Ausschnitt (WFS) | GeoPackage | – | je nach Gebiet |
| `alkis` | ALKIS vereinfacht je Kreis (GeoPackage) | je Kreis/Bezirk | GeoPackage (ZIP) | 53 | 7,4 GB |
| `alkis-nas` | ALKIS Grundrissdaten je Kreis (NAS) | je Kreis/Bezirk | NAS-XML (ZIP) | 53 | 20,8 GB |
| `alkis-hist` | ALKIS vereinfacht, Jahresstände (GeoPackage) | je Kreis/Bezirk | GeoPackage (ZIP) | 10 Jahrgänge (2016–2025) | – |
| `abk` | Amtliche Basiskarte farbig (ABK) | Kacheln | GeoTIFF | 35.022 | 53,9 GB |
| `abk-sw` | Amtliche Basiskarte schwarz-weiß (ABK) | Kacheln | GeoTIFF | 35.022 | 15,1 GB |
| `hauskoordinaten` | Gebäudereferenzen / Hauskoordinaten (ASCII) | landesweit | CSV/ASCII (ZIP) | 1 | 97,0 MB |

## Karten

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `dtk25` | Digitale Topographische Karte 1:25 000 (farbig) | Kacheln | GeoTIFF | 2.336 | 2,3 GB |
| `dtk50` | Digitale Topographische Karte 1:50 000 (farbig) | Kacheln | GeoTIFF | 635 | 692,2 MB |
| `dtk100` | Digitale Topographische Karte 1:100 000 (farbig) | Kacheln | GeoTIFF | 178 | 169,8 MB |
| `dgk5` | Deutsche Grundkarte 1:5 000 (historisch, Grundriss) | Kacheln | GeoTIFF | 9.217 | 4,7 GB |

## Landschaftsmodelle

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `basis-dlm` | Digitales Basis-Landschaftsmodell (Basis-DLM) | landesweit | Shape oder NAS (ZIP) | 1 | 4,7 GB |
| `dlm50` | Digitales Landschaftsmodell 1:50 000 (DLM50) | landesweit | Shape oder NAS (ZIP) | 1 | 3,0 GB |

## Verwaltungsgrenzen

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `dvg1` | Verwaltungsgrenzen, hohe Stützpunktdichte (DVG1) | landesweit | Shape/TIFF/ASCII (ZIP) | 1 | 22,5 MB |
| `dvg2` | Verwaltungsgrenzen, generalisiert (DVG2) | landesweit | Shape/TIFF/ASCII (ZIP) | 1 | 2,6 MB |

## Weitere

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `bodenbewegung` | Höhenänderungen aus Sentinel-1 (Bodenbewegung) | Kacheln | GeoPackage | 155 | 48,3 GB |
| `freizeit` | Touristik- und Freizeitinformationen (TFIS) | landesweit | GeoPackage (ZIP) | 1 | 26,9 MB |

# Niedersachsen

Lizenz: Creative Commons Namensnennung 4.0 (CC BY 4.0). Namensnennung: „Quelle: LGLN (Jahr), CC BY 4.0“.

## Höhenmodelle

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `dgm1` | Digitales Geländemodell 1 m (DGM1) | Kacheln | Cloud-Optimized GeoTIFF | – | – |
| `dom1` | Digitales Oberflächenmodell 1 m (DOM1) | Kacheln | Cloud-Optimized GeoTIFF | – | – |
| `bdom20` | Bildbasiertes Oberflächenmodell 20 cm (bDOM20) | Kacheln | Cloud-Optimized GeoTIFF | – | – |

## Luftbilder

| ID | Titel | Art | Format | Dateien | Gesamtgröße |
|---|---|---|---|---:|---:|
| `dop20` | Digitale Orthophotos 20 cm (DOP20) | Kacheln | Cloud-Optimized GeoTIFF | – | – |
| `dop10` | Digitale Orthophotos 10 cm (DOP10, neue Befliegungen) | Kacheln | Cloud-Optimized GeoTIFF | – | – |
| `dop-hist` | Historische Orthophotos 20 cm (Luftbildarchiv) | Kacheln | Cloud-Optimized GeoTIFF | 15 Jahrgänge (2012–2026) | – |

