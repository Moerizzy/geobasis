"""Kommandozeile: ``geobasis <befehl> ...`` (siehe ``geobasis --help``)."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys

from . import bund, http
from ._version import __version__
from .laender import LAENDER, land
from .models import RemoteFile, Selection, format_size

CONFIRM_ABOVE = 5_000_000_000  # bytes; larger downloads need --ja

EPILOG = """Beispiele:
  geobasis produkte
  geobasis suche dgm1 --gemeinde "Bad Honnef"
  geobasis suche dgm1 --bbox 7.9,52.2,8.1,52.4        # NRW und Niedersachsen zusammen
  geobasis download dop10 --punkt 6.958,50.941 --radius 500 -o daten
  geobasis download flurstuecke --gemeinde Münster -o daten
  geobasis jahre dop-hist --punkt 7.626,51.962
  geobasis download dop-hist --jahr 1969 --punkt 7.626,51.962 -o daten
  geobasis portal geobasis/hm
"""


def _add_area(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("Gebiet (höchstens eine Angabe; ohne Angabe: ganzes Land)")
    g.add_argument("--gemeinde", "--municipality", metavar="NAME|AGS",
                   help="Gemeinde/Stadt, z. B. 'Münster' oder 05515000")
    g.add_argument("--kreis", "--district", metavar="NAME|AGS", help="Kreis oder kreisfreie Stadt")
    g.add_argument("--regbez", metavar="NAME|AGS", help="Regierungsbezirk, z. B. Detmold")
    g.add_argument("--bbox", metavar="MINX,MINY,MAXX,MAXY",
                   help="Rechteck in Grad (Länge/Breite) oder in Metern (UTM32)")
    g.add_argument("--punkt", "--point", metavar="X,Y", help="Punkt, z. B. 6.958,50.941")
    g.add_argument("--radius", type=float, default=0.0, metavar="METER",
                   help="Radius um --punkt in Metern (Standard 0)")
    g.add_argument("--geojson", metavar="DATEI", help="Gebiet aus GeoJSON-Datei")
    g.add_argument("--crs", metavar="EPSG", help="Koordinatensystem für --bbox/--punkt/--geojson")


def _area_kw(a: argparse.Namespace) -> dict:
    return dict(gemeinde=a.gemeinde, kreis=a.kreis, regbez=a.regbez, bbox=a.bbox,
                point=a.punkt, radius=a.radius, geojson=a.geojson, crs=a.crs)


def _add_select(p: argparse.ArgumentParser) -> None:
    p.add_argument("produkt", help="Produkt-ID, siehe 'geobasis produkte'")
    p.add_argument("--jahr", "--year", type=int, help="Jahrgang bei Archivprodukten")
    p.add_argument("--variante", "--variant", help="Formatvariante, z. B. shape oder nas")
    p.add_argument("--alle-fassungen", action="store_true",
                   help="bei doppelt vorhandenen Kacheln alle Jahrgänge statt nur des neuesten")
    _add_area(p)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="geobasis", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EPILOG,
        description="Amtliche Geobasisdaten finden und herunterladen "
                    "(derzeit Nordrhein-Westfalen und Niedersachsen).")
    ap.add_argument("--version", action="version", version=f"geobasis {__version__}")
    land_help = f"nur dieses Land ({', '.join(LAENDER)}); ohne Angabe: alle"
    ap.add_argument("--land", default=None, help=land_help)
    common = argparse.ArgumentParser(add_help=False)  # --land also after the command
    common.add_argument("--land", default=argparse.SUPPRESS, help=land_help)
    sub = ap.add_subparsers(dest="cmd", metavar="BEFEHL")
    _add = sub.add_parser

    def add_parser(*args, **kw):
        return _add(*args, parents=[common], **kw)

    sub.add_parser = add_parser  # type: ignore[method-assign]

    p = sub.add_parser("produkte", aliases=["products", "liste"], help="verfügbare Produkte")
    p.add_argument("--kategorie", help="nur eine Kategorie, z. B. Höhenmodelle")
    p.add_argument("--json", action="store_true", help="Ausgabe als JSON")

    p = sub.add_parser("info", help="Details zu einem Produkt")
    p.add_argument("produkt")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("jahre", aliases=["years"],
                       help="Jahrgänge eines Archivprodukts (mit Gebiet: Abdeckung je Jahr)")
    p.add_argument("produkt")
    _add_area(p)

    p = sub.add_parser("suche", aliases=["find", "search"], help="Dateien für ein Gebiet anzeigen")
    _add_select(p)
    p.add_argument("--json", action="store_true", help="vollständige Liste als JSON")
    p.add_argument("--umrisse", "--footprints", dest="out_geojson", metavar="DATEI",
                   help="Kachelumrisse als GeoJSON speichern (z. B. für QGIS)")
    p.add_argument("--zeilen", type=int, default=20, help="max. angezeigte Zeilen (Standard 20)")
    p.add_argument("--ohne-metadaten", action="store_true", help="Kachel-Metadaten nicht laden")

    p = sub.add_parser("download", aliases=["get", "laden"], help="Dateien herunterladen")
    _add_select(p)
    p.add_argument("-o", "--ziel", "--out", default=".", help="Zielordner (Standard: .)")
    p.add_argument("--parallel", "--workers", type=int, default=4,
                   help="gleichzeitige Downloads (Standard 4, max. 16)")
    p.add_argument("--probelauf", "--dry-run", action="store_true",
                   help="nur anzeigen, was geladen würde")
    p.add_argument("--vrt", action="store_true", help="Raster-Mosaik als GDAL-VRT anlegen")
    p.add_argument("--entpacken", "--extract", action="store_true", help="ZIP-Dateien entpacken")
    p.add_argument("--ueberschreiben", "--overwrite", action="store_true",
                   help="vorhandene Dateien neu laden")
    p.add_argument("-y", "--ja", "--yes", action="store_true",
                   help=f"ohne Rückfrage, auch über {format_size(CONFIRM_ABOVE)}")

    p = sub.add_parser("gemeinden", aliases=["orte", "places"],
                       help="Gemeinden, Kreise oder Regierungsbezirke auflisten")
    p.add_argument("suche", nargs="?", help="Teil des Namens oder Schlüssels")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--kreise", action="store_true", help="Kreise statt Gemeinden")
    grp.add_argument("--regbez", action="store_true", help="Regierungsbezirke")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("dienste", aliases=["services"], help="WMS/WFS-Adressen für GIS-Programme")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("portal", help="Open-Data-Portal direkt durchsuchen und Dateien laden")
    p.add_argument("pfad", nargs="?", default="", help="Ordner, z. B. geobasis/hm")
    p.add_argument("--laden", nargs="+", metavar="MUSTER",
                   help="Dateien im Ordner laden (Platzhalter erlaubt, z. B. '*.zip')")
    p.add_argument("-o", "--ziel", default=".", help="Zielordner für --laden")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("cache", help="Zwischenspeicher anzeigen oder leeren")
    p.add_argument("--leeren", "--clear", action="store_true")
    return ap


def _table(rows: list[list[str]], headers: list[str]) -> str:
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    lines = [fmt.format(*headers), fmt.format(*["-" * w for w in widths])]
    lines += [fmt.format(*[str(c) for c in r]) for r in rows]
    return "\n".join(line.rstrip() for line in lines)


def _print_notes(sel: Selection) -> None:
    for n in sel.notes:
        print(f"Hinweis: {n}")


def _lands(a) -> list:
    return [land(a.land)] if a.land else list(LAENDER.values())


def cmd_produkte(a) -> int:
    lands = _lands(a)
    if a.json:
        print(json.dumps([p.info() for lnd in lands for p in lnd.products(a.kategorie)],
                         ensure_ascii=False, indent=1))
        return 0
    for lnd in lands:
        ps = lnd.products(a.kategorie)
        if not ps:
            continue
        print(f"\n=== {lnd.name} ({lnd.code}) – Lizenz: {lnd.license}")
        for cat in lnd.categories():
            rows = [[p.id, p.title, p.format, p.resolution] for p in ps if p.category == cat]
            if rows:
                print(f"\n{cat}")
                print(_table(rows, ["ID", "Titel", "Format", "Auflösung"]))
    return 0


def cmd_info(a) -> int:
    found = [lnd.product(a.produkt) for lnd in _lands(a) if lnd.has_product(a.produkt)]
    if not found:
        bund.find(a.produkt, land=a.land)  # raises KeyError with suggestions
    out = []
    for p in found:
        d = p.info()
        if p.aliases:
            d["aliase"] = ", ".join(p.aliases)
        if p.yearly:
            d["jahrgaenge"] = ", ".join(map(str, p.years()))
        elif p.kind != "wfs" and p.enumerable:
            sel = p.find(None, with_meta=False)
            d["dateien"] = f"{len(sel)} ({format_size(sel.total_size)} gesamt)"
        out.append(d)
    if a.json:
        print(json.dumps(out if len(out) > 1 else out[0], ensure_ascii=False, indent=1))
        return 0
    for i, d in enumerate(out):
        if i:
            print()
        w = max(len(k) for k in d)
        for k, v in d.items():
            print(f"{k:<{w}}  {', '.join(v) if isinstance(v, list) else v}")
    return 0


def cmd_jahre(a) -> int:
    area, lands = bund.area(land=a.land, **_area_kw(a))
    products = [lnd.product(a.produkt) for lnd in lands if lnd.has_product(a.produkt)]
    if not products:
        bund.find(a.produkt, land=a.land, **_area_kw(a))  # raises KeyError with suggestions
    archives = [p for p in products if p.yearly]
    if not archives:
        print(f"'{a.produkt}' ist kein Archivprodukt (nur aktueller Stand).")
        return 0
    for p in archives:
        prefix = f"{p.land.upper()}: " if len(archives) > 1 else ""
        if area is None:
            print(prefix + " ".join(map(str, p.years())))
            continue
        print(f"{prefix}Abdeckung für {area.label} (kann beim ersten Mal etwas dauern) ...",
              file=sys.stderr)
        cov = p.coverage(area)
        if len(archives) > 1:
            print(f"\n{p.land.upper()} – {p.title}")
        print(_table([[str(y), str(n)] for y, n in cov.items() if n], ["Jahr", "Dateien"]))
        missing = [str(y) for y, n in cov.items() if not n]
        if missing:
            print(f"\nOhne Daten im Gebiet: {', '.join(missing)}")
    return 0


def _selection(a) -> Selection:
    return bund.find(a.produkt, land=a.land, year=a.jahr, variant=a.variante,
                     latest=not a.alle_fassungen,
                     with_meta=not getattr(a, "ohne_metadaten", False), **_area_kw(a))


def cmd_suche(a) -> int:
    sel = _selection(a)
    if a.out_geojson:
        sel.save_geojson(a.out_geojson)
    if a.json:
        print(json.dumps([f.to_dict() for f in sel], ensure_ascii=False, indent=1))
        return 0
    print(sel.summary())
    _print_notes(sel)
    multi = len({f.land for f in sel}) > 1
    rows = []
    for f in sel[: a.zeilen]:
        row = [f.name, format_size(f.size), f.date or (str(f.year) if f.year else ""),
               f.meta.get("Kreis") or f.meta.get("Regierungsbezirk") or f.key or ""]
        rows.append(([f.land.upper()] if multi else []) + row)
    if rows:
        head = ["Datei", "Größe", "Stand", "Kachel/Gebiet"]
        print(_table(rows, (["Land"] if multi else []) + head))
    if len(sel) > a.zeilen:
        print(f"... und {len(sel) - a.zeilen} weitere (--zeilen N oder --json für alle)")
    if a.out_geojson:
        print(f"Umrisse gespeichert: {a.out_geojson}")
    return 0


def cmd_download(a) -> int:
    sel = _selection(a)

    print(sel.summary())
    _print_notes(sel)
    if not sel:
        return 0
    if a.probelauf:
        for f in sel:
            print(f"  {f.url}  ({format_size(f.size)})")
        return 0
    if sel.total_size > CONFIRM_ABOVE and not a.ja:
        if sys.stdin.isatty():
            ans = input(f"{format_size(sel.total_size)} herunterladen? [j/N] ").strip().lower()
            if ans not in ("j", "ja", "y", "yes"):
                print("Abgebrochen.")
                return 1
        else:
            print(f"Abbruch: {format_size(sel.total_size)} ist viel - zum Bestätigen --ja angeben.",
                  file=sys.stderr)
            return 1
    res = sel.download(a.ziel, workers=a.parallel, overwrite=a.ueberschreiben, vrt=a.vrt,
                       extract=a.entpacken)
    print(res.summary())
    for f, err in res.failed:
        print(f"  FEHLER {f.name}: {err}", file=sys.stderr)
    if res.vrt:
        print(f"Mosaik: {res.vrt}")
    if res.manifest:
        print(f"Herkunft und Lizenz: {res.manifest}")
    return 0 if res.ok else 1


def cmd_gemeinden(a) -> int:
    units = []
    for lnd in _lands(a):
        if a.kreise:
            units += lnd.kreise(a.suche)
        elif a.regbez:
            units += lnd.regierungsbezirke(a.suche)
        else:
            units += lnd.gemeinden(a.suche)
    what = "Kreise" if a.kreise else "Regierungsbezirke" if a.regbez else "Gemeinden"
    if a.json:
        print(json.dumps([{"name": u.name, "ags": u.ags, "art": u.bez, "land": u.land,
                           "bbox": u.bbox.as_tuple()} for u in units], ensure_ascii=False, indent=1))
        return 0
    print(_table([[u.land.upper(), u.ags, u.name, u.bez] for u in units],
                 ["Land", "Schlüssel", "Name", "Art"]))
    print(f"\n{len(units)} {what}")
    return 0


def cmd_dienste(a) -> int:
    svc = [dict(s, land=lnd.code) for lnd in _lands(a) for s in lnd.services()]
    if a.json:
        print(json.dumps(svc, ensure_ascii=False, indent=1))
        return 0
    if not svc:
        print("Für dieses Land sind noch keine Dienste hinterlegt.")
        return 0
    print(_table([[s["land"].upper(), s["typ"], s["titel"], s["url"]] for s in svc],
                 ["Land", "Typ", "Titel", "URL"]))
    return 0


def cmd_portal(a) -> int:
    lnd = land(a.land or "nw")
    portal = getattr(lnd, "portal", None)
    if portal is None:
        print(f"Für {lnd.short} gibt es keinen Portal-Browser.", file=sys.stderr)
        return 1
    lst = portal.listing(a.pfad)
    if a.laden:
        files = [f for f in lst.files + lst.metafiles
                 if any(fnmatch.fnmatch(f.name, m) for m in a.laden)]
        if not files:
            print("Keine passenden Dateien.", file=sys.stderr)
            return 1
        sel = Selection([RemoteFile(name=f.name, url=f.url, size=f.size, modified=f.timestamp)
                         for f in files])
        from .download import download_selection

        res = download_selection(sel, a.ziel, manifest=False)
        print(res.summary())
        return 0 if res.ok else 1
    if a.json:
        print(json.dumps({"ordner": lst.folders,
                          "dateien": [f.__dict__ for f in lst.files],
                          "beilagen": [f.__dict__ for f in lst.metafiles]},
                         ensure_ascii=False, indent=1))
        return 0
    print(portal.url_for(lst.path))
    if lst.folders:
        print(_table([[f["name"] + "/", f.get("title", "")] for f in lst.folders],
                     ["Ordner", "Titel"]))
    if lst.files:
        shown = lst.files[:50]
        print(_table([[f.name, format_size(f.size), (f.timestamp or "")[:10]] for f in shown],
                     ["Datei", "Größe", "Stand"]))
        if len(lst.files) > 50:
            total = sum(f.size or 0 for f in lst.files)
            print(f"... insgesamt {len(lst.files)} Dateien, {format_size(total)}")
    if lst.metafiles:
        print("Beilagen: " + ", ".join(m.name for m in lst.metafiles))
    return 0


def cmd_cache(a) -> int:
    d = http.cache_dir()
    if a.leeren:
        n = http.clear_cache()
        print(f"{n} Dateien gelöscht ({d})")
        return 0
    files = [p for p in (d / "http").rglob("*") if p.is_file()] if (d / "http").exists() else []
    print(f"{d}: {len(files)} Dateien, {format_size(sum(p.stat().st_size for p in files))}")
    return 0


COMMANDS = {
    "produkte": cmd_produkte, "products": cmd_produkte, "liste": cmd_produkte,
    "info": cmd_info, "jahre": cmd_jahre, "years": cmd_jahre,
    "suche": cmd_suche, "find": cmd_suche, "search": cmd_suche,
    "download": cmd_download, "get": cmd_download, "laden": cmd_download,
    "gemeinden": cmd_gemeinden, "orte": cmd_gemeinden, "places": cmd_gemeinden,
    "dienste": cmd_dienste, "services": cmd_dienste, "portal": cmd_portal, "cache": cmd_cache,
}


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 0
    try:
        return COMMANDS[a.cmd](a)
    except (KeyError, LookupError, ValueError) as e:
        msg = e.args[0] if e.args else str(e)
        print(f"Fehler: {msg}", file=sys.stderr)
        return 2
    except http.HTTPError as e:
        print(f"Fehler beim Abruf: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAbgebrochen (erneuter Aufruf setzt angefangene Downloads fort).", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
