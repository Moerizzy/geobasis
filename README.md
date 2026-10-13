# geobasis

**Amtliche Geodaten mit einer Zeile Python.** Derzeit für Nordrhein-Westfalen und Niedersachsen.

> Inoffizielles Open-Source-Werkzeug. Alle Daten kommen direkt von den Servern der Länder.

Die Länder stellen Höhenmodelle, Luftbilder, Kataster- und 3D-Gebäudedaten frei
bereit, aber jedes über eigene Portale und Formate. `geobasis` sucht für ein
Gebiet die passenden Dateien, auch über Landesgrenzen hinweg, und lädt sie
herunter.

```bash
pip install geobasis
geobasis suche dgm1 --gemeinde Münster                 # was würde geladen?
geobasis download dop --punkt 6.958,50.941 --radius 500 -o daten
geobasis download dgm1 --bbox 7.95,52.15,8.0,52.19 -o daten --vrt   # NRW + NI
geobasis jahre dop-hist --punkt 7.626,51.962           # Luftbilder seit 1951
```

```python
import geobasis

sel = geobasis.find("dgm1", gemeinde="Münster")
print(sel.summary())
sel.download("daten")
```

Gebiete gibt man als Gemeinde, Kreis, Punkt mit Radius, Rechteck oder GeoJSON an.
Jeder Download enthält eine `manifest.json` mit Quelle, Lizenz und Aufnahmedatum
je Kachel. Alle Befehle: `geobasis --help`, alle Produkte:
[docs/produkte.md](docs/produkte.md), Aufbau: [docs/architektur.md](docs/architektur.md).

## Datenlizenzen

| Land | Lizenz | Namensnennung |
|---|---|---|
| Nordrhein-Westfalen | [dl-de/zero-2-0](https://www.govdata.de/dl-de/zero-2-0) | erwünscht: „Land NRW (Jahr)“ |
| Niedersachsen | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de) | **Pflicht:** „Quelle: LGLN (Jahr), CC BY 4.0“ |

## Entwicklung

```bash
pip install -e ".[dev]"
pytest              # offline gegen nachgebaute Dienste
pytest -m online    # gegen die echten Server
```

Beiträge sind willkommen, siehe [CONTRIBUTING.md](CONTRIBUTING.md). Code: [MIT](LICENSE).

*English:* `geobasis` downloads official open geodata of German states (currently
NRW and Lower Saxony) for any area with one line of Python. Pure Python, no dependencies.
