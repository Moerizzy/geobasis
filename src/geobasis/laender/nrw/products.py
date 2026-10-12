"""Product definitions for NRW and how to find their files."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from ...area import Area
from ...geo import ShapeIndex
from ...models import Product, RemoteFile, Selection
from ...tiles import parse_tile, parse_year
from . import grenzen, portal, wfs

LICENSE = "Datenlizenz Deutschland – Zero – Version 2.0 (dl-de/zero-2-0)"
LICENSE_URL = "https://www.govdata.de/dl-de/zero-2-0"
_AGS = re.compile(r"_(05\d{6})_")


@dataclass
class NrwProduct(Product):
    path: str = ""
    file_regex: str = ""
    meta_date: str | None = None

    def __post_init__(self):
        self.land = "nw"
        self.license = self.license or LICENSE
        if not self.source and self.path:
            self.source = portal.url_for(self.path.split("{", 1)[0])

    def _accept(self, name: str) -> bool:
        return not self.file_regex or re.search(self.file_regex, name) is not None


def _latest_per_key(files: list[RemoteFile]) -> list[RemoteFile]:
    best: dict[str, RemoteFile] = {}
    for f in files:
        k = f.key or f.name
        cur = best.get(k)
        if cur is None or ((f.year or 0), f.name) > ((cur.year or 0), cur.name):
            best[k] = f
    return list(best.values())


def tiles_from_listing(product: NrwProduct, lst: portal.Listing, area: Area | None, crs: int,
                       *, latest: bool, with_meta: bool, year: int | None = None,
                       subdir: str = "") -> list[RemoteFile]:
    refs = []
    sizes: Counter = Counter()
    for f in lst.files:
        if not product._accept(f.name):
            continue
        ref = parse_tile(f.name, crs)
        if ref is None:
            continue
        refs.append((f, ref))
        if ref.size:
            sizes[ref.size] += 1
    default = sizes.most_common(1)[0][0] if sizes else (1000.0 if crs == 25832 else 2000.0)
    idx = None
    if area is not None:
        idx = ShapeIndex(area.shape.transform(crs))
    out: list[RemoteFile] = []
    for f, ref in refs:
        b = ref.bounds(default)
        if idx is not None and not idx.intersects_rect(*b):
            continue
        out.append(RemoteFile(name=f.name, url=f.url, size=f.size, modified=f.timestamp,
                              product=product.id, crs=crs, bounds=b, key=ref.key,
                              year=parse_year(f.name) or year, subdir=subdir))
    if latest:
        out = _latest_per_key(out)
    if with_meta and out:
        mf = next((m for m in lst.metafiles if m.name.lower().endswith("meta.zip")), None)
        table = portal.load_meta(mf.url, crs) if mf else None
        if table:
            for rf in out:
                row = table.lookup(rf.name, rf.key)
                if row:
                    rf.meta = {k: v for k, v in row.items() if v}
                    rf.date = table.date_of(row, product.meta_date)
    out.sort(key=lambda r: (r.key or "", r.name))
    return out


@dataclass
class TileProduct(NrwProduct):
    """Regular grid tiles named after their lower-left corner."""

    def __post_init__(self):
        super().__post_init__()
        self.kind = "tiles"

    def _find(self, area, *, year, variant, latest, with_meta) -> Selection:
        lst = portal.listing(self.path)
        files = tiles_from_listing(self, lst, area, 25832, latest=latest, with_meta=with_meta)
        return Selection(files, self, area)


@dataclass
class HistDopProduct(NrwProduct):
    """Historic orthophotos: one folder per year, inside one folder per CRS.

    1951-2009 are delivered in Gauß-Krüger (EPSG:31466 *and* 31467 for the
    overlap of both strips), from 2010 in ETRS89/UTM32."""

    root: str = "geobasis/lusat/hist/hist_dop/hist_dop_jp2_f10/"

    def __post_init__(self):
        super().__post_init__()
        self.kind = "tiles"
        self.yearly = True
        self.source = portal.url_for(self.root)

    def years(self) -> list[int]:
        lst = portal.listing(self.root)
        ys = []
        for f in lst.folders:
            m = re.fullmatch(r"hist_dop_(\d{4})", f.get("name", ""))
            if m:
                ys.append(int(m.group(1)))
        return sorted(ys)

    def _find(self, area, *, year, variant, latest, with_meta) -> Selection:
        ys = self.years()
        if year not in ys:
            raise ValueError(f"Jahrgang {year} gibt es nicht (verfügbar: {ys[0]}–{ys[-1]}, "
                             f"Lücken möglich; siehe 'geobasis jahre {self.id}')")
        ypath = f"{self.root}hist_dop_{year}/"
        results: dict[int, list[RemoteFile]] = {}
        for folder in portal.listing(ypath).folders:
            m = re.fullmatch(r"epsg_(\d+)", folder.get("name", ""))
            if not m:
                continue
            code = int(m.group(1))
            sub = portal.listing(ypath + folder["name"])
            results[code] = tiles_from_listing(self, sub, area, code, latest=latest,
                                               with_meta=with_meta, year=year, subdir=str(year))
        notes = []
        nonempty = {c: r for c, r in results.items() if r}
        if len(nonempty) > 1 and area is not None:
            lon = area.shape.centroid_lonlat()[0]
            prefer = 31466 if lon < 7.5 else 31467
            code = prefer if prefer in nonempty else next(iter(nonempty))
            notes.append(f"Jahrgang {year} liegt in mehreren Gauß-Krüger-Streifen vor; "
                         f"gewählt: EPSG:{code}.")
            files = nonempty[code]
        else:
            files = [f for r in nonempty.values() for f in r]
            if len(nonempty) > 1:
                notes.append("Ohne Gebiet werden beide Gauß-Krüger-Streifen geliefert; "
                             "die Überlappung ist dann doppelt enthalten.")
        return Selection(files, self, area, notes)


@dataclass
class AdminProduct(NrwProduct):
    """One file per district (Kreis) or administrative region (Regierungsbezirk)."""

    level: str = "kreis"

    def __post_init__(self):
        super().__post_init__()
        self.kind = "admin"

    def years(self) -> list[int]:
        if not self.yearly:
            return []
        parent = self.path.split("{year}")[0]
        return sorted(int(f["name"]) for f in portal.listing(parent).folders
                      if re.fullmatch(r"\d{4}", f.get("name", "")))

    def _find(self, area, *, year, variant, latest, with_meta) -> Selection:
        if self.yearly and year not in self.years():
            raise ValueError(f"Jahrgang {year} gibt es nicht (verfügbar: "
                             f"{', '.join(map(str, self.years()))})")
        path = self.path.format(year=year) if self.yearly else self.path
        lst = portal.listing(path)
        n = 5 if self.level == "kreis" else 3
        units = {u.ags[:n]: u for u in grenzen.units(self.level)}
        want = None
        if area is not None:
            want = {u.ags[:n] for u in grenzen.units_for(self.level, area)}
        out = []
        for f in lst.files:
            m = _AGS.search(f.name)
            if not m or not self._accept(f.name):
                continue
            ags = m.group(1)
            if want is not None and ags[:n] not in want:
                continue
            u = units.get(ags[:n])
            out.append(RemoteFile(
                name=f.name, url=f.url, size=f.size, modified=f.timestamp, product=self.id,
                key=ags, year=year, crs=25832, bounds=u.bbox.as_tuple() if u else None,
                subdir=str(year) if year else "",
                meta={grenzen.LEVEL_NAMES[self.level]: u.name} if u else {}))
        return Selection(sorted(out, key=lambda r: r.key or ""), self, area)


@dataclass
class SingleProduct(NrwProduct):
    """A state-wide file (optionally in several formats = variants)."""

    def __post_init__(self):
        super().__post_init__()
        self.kind = "single"

    def _find(self, area, *, year, variant, latest, with_meta) -> Selection:
        lst = portal.listing(self.path)
        rx = self.variants.get(variant) if variant else None
        out = []
        for f in lst.files:
            if not self._accept(f.name):
                continue
            if rx and not (re.search(rx, f.name) or re.search(rx, f.dataset)):
                continue
            out.append(RemoteFile(name=f.name, url=f.url, size=f.size, modified=f.timestamp,
                                  product=self.id))
        notes = ["Dieses Produkt gibt es nur landesweit; die Gebietsangabe wird ignoriert."] if area else []
        return Selection(out, self, area, notes)


@dataclass
class WfsProduct(NrwProduct):
    """Objects of one ALKIS class cut out for the area via WFS (GeoPackage)."""

    typename: str = ""
    warn_above: int = 300_000

    def __post_init__(self):
        super().__post_init__()
        self.kind = "wfs"
        self.source = wfs.ALKIS_WFS

    def _find(self, area, *, year, variant, latest, with_meta) -> Selection:
        if area is None:
            raise ValueError(f"'{self.id}' braucht ein Gebiet (z. B. --gemeinde). "
                             "Ganze Kreise lädt man schneller mit dem Produkt 'alkis'.")
        n = wfs.count(self.typename, area.shape)
        if n == 0:
            return Selection([], self, area, ["Keine Objekte im Gebiet."])
        slug = re.sub(r"[^a-z0-9]+", "-", _ascii(area.label.lower())).strip("-")[:60]
        rf = RemoteFile(name=f"{self.id}_{slug}.gpkg", url=wfs.ALKIS_WFS, size=None,
                        product=self.id, crs=25832, bounds=area.shape.bbox.as_tuple(),
                        meta={"objekte": n, "objektart": self.typename},
                        post_data=wfs.getfeature_body(self.typename, area.shape))
        notes = [f"{n} Objekte im Gebiet."]
        if n > self.warn_above:
            notes.append("Das ist viel für einen WFS-Abruf; für ganze Kreise ist das Produkt "
                         "'alkis' schneller.")
        return Selection([rf], self, area, notes)


def _ascii(s: str) -> str:
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return s


# --------------------------------------------------------------------------
# The catalogue
# --------------------------------------------------------------------------

HM, LB, GEB, KAT, KARTE, LM, VG, SONST = (
    "Höhenmodelle", "Luftbilder", "3D-Gebäude", "Liegenschaftskataster", "Karten",
    "Landschaftsmodelle", "Verwaltungsgrenzen", "Weitere")


def build_products() -> list[Product]:
    g = "geobasis/"
    return [
        # Höhenmodelle ------------------------------------------------------------
        TileProduct("dgm1", "Digitales Geländemodell 1 m (DGM1)", HM, "tiles", "GeoTIFF", "1 m",
                    description="Höhe der Erdoberfläche ohne Bewuchs und Bebauung, 1-km-Kacheln, "
                                "Höhen in m über NHN (DHHN2016).",
                    path=g + "hm/dgm1_tiff/dgm1_tiff/", file_regex=r"\.tif$", raster=True,
                    aliases=("dgm", "gelaendemodell")),
        TileProduct("dom1", "Digitales Oberflächenmodell 1 m (DOM1)", HM, "tiles", "GeoTIFF", "1 m",
                    description="Höhe der Oberfläche inklusive Gebäude und Vegetation, 1-km-Kacheln.",
                    path=g + "hm/dom1_tiff/dom1_tiff/", file_regex=r"\.tif$", raster=True,
                    aliases=("dom",)),
        TileProduct("ndom50", "Normalisiertes Oberflächenmodell 50 cm (nDOM50)", HM, "tiles",
                    "GeoTIFF", "0,5 m",
                    description="Objekthöhen über Grund (DOM minus DGM), z. B. Gebäude- und "
                                "Baumhöhen.",
                    path=g + "hm/ndom50_tiff/ndom50_tiff/", file_regex=r"\.tif$", raster=True,
                    meta_date="Aufnahmedatum_bDOM", aliases=("ndom",)),
        TileProduct("bdom50", "Bildbasiertes Oberflächenmodell 50 cm (bDOM50)", HM, "tiles",
                    "LAZ (Punktwolke)", "0,5 m",
                    description="Aus Luftbildern abgeleitete, gegitterte Punktwolke mit Farbe "
                                "(RGBI), aktueller als das Laser-DOM.",
                    path=g + "hm/bdom50_las/bdom50_las/", file_regex=r"\.laz$",
                    aliases=("bdom",)),
        TileProduct("laserscan", "3D-Messdaten Laserscanning (Punktwolke)", HM, "tiles",
                    "LAZ (Punktwolke)", "≈ 4 Punkte/m²",
                    description="Klassifizierte Airborne-Laserscanning-Punktwolke, ca. 100 MB je km².",
                    path=g + "hm/3dm_l_las/3dm_l_las/", file_regex=r"\.laz$",
                    aliases=("3dm", "als", "lidar", "punktwolke")),
        # Luftbilder --------------------------------------------------------------
        TileProduct("dop10", "Digitale Orthophotos 10 cm (DOP10, RGBI)", LB, "tiles", "JPEG 2000",
                    "0,1 m",
                    description="Aktuelle entzerrte Luftbilder in Farbe und Infrarot, 1-km-Kacheln.",
                    path=g + "lusat/akt/dop/dop_jp2_f10/", file_regex=r"\.jp2$", raster=True,
                    aliases=("dop", "luftbild", "orthophoto")),
        TileProduct("idop20", "InVeKoS-Orthophotos 20 cm (iDOP20, RGBI)", LB, "tiles",
                    "JPEG 2000", "0,2 m",
                    description="Orthophotos aus der Agrarförderung (InVeKoS), jährlich erneuert.",
                    path=g + "lusat/akt/idop/idop_jp2_f2/", file_regex=r"\.jp2$", raster=True,
                    aliases=("idop",)),
        HistDopProduct("dop-hist", "Historische Orthophotos (Luftbildarchiv seit 1951)", LB,
                       "tiles", "JPEG 2000", "0,1–0,4 m",
                       description="Jahrgänge 1951 bis heute; bis 2009 in Gauß-Krüger, danach UTM. "
                                   "Abdeckung je Jahrgang unterschiedlich.",
                       raster=True, aliases=("dop_hist", "luftbildarchiv", "historisch")),
        AdminProduct("landbedeckung", "Landbedeckung NRW (GeoPackage)", LB, "admin",
                     "GeoPackage (ZIP)", "",
                     description="Flächendeckende Landbedeckungsklassen, je Regierungsbezirk.",
                     path=g + "lusat/akt/lb_nrw/", level="regbez", aliases=("lb", "lb_nrw")),
        # 3D-Gebäude --------------------------------------------------------------
        TileProduct("lod2", "3D-Gebäudemodell LoD2 (CityGML)", GEB, "tiles", "CityGML", "",
                    description="Gebäude mit Dachformen, 1-km-Kacheln.",
                    path=g + "3dg/lod2_gml/lod2_gml/", file_regex=r"\.gml$",
                    aliases=("3d", "gebaeude3d")),
        TileProduct("lod1", "3D-Gebäudemodell LoD1 (CityGML)", GEB, "tiles", "CityGML", "",
                    description="Gebäude als Klötzchenmodell mit Flachdach, 1-km-Kacheln.",
                    path=g + "3dg/lod1_gml/lod1_gml/", file_regex=r"\.gml$"),
        # Liegenschaftskataster ---------------------------------------------------
        WfsProduct("flurstuecke", "Flurstücke (ALKIS, Ausschnitt per WFS)", KAT, "wfs",
                   "GeoPackage", "", typename="ave:Flurstueck",
                   description="Flurstücke mit Kennzeichen, Fläche, Lage; ohne Eigentümer.",
                   aliases=("flurstueck", "parzellen")),
        WfsProduct("gebaeude", "Gebäude (ALKIS, Ausschnitt per WFS)", KAT, "wfs", "GeoPackage", "",
                   typename="ave:GebaeudeBauwerk",
                   description="Gebäudegrundrisse mit Funktion und Geschosszahl.",
                   aliases=("gebaeudegrundrisse", "hausumringe")),
        WfsProduct("nutzung", "Tatsächliche Nutzung (ALKIS, Ausschnitt per WFS)", KAT, "wfs",
                   "GeoPackage", "", typename="ave:Nutzung",
                   description="Flächen der tatsächlichen Nutzung (Wohnbau, Wald, Acker, ...).",
                   aliases=("tn", "landnutzung")),
        WfsProduct("katasterbezirke", "Gemarkungen und Fluren (ALKIS, per WFS)", KAT, "wfs",
                   "GeoPackage", "", typename="ave:KatasterBezirk",
                   aliases=("gemarkungen", "fluren")),
        WfsProduct("verwaltungseinheiten", "Verwaltungseinheiten (ALKIS, per WFS)", KAT, "wfs",
                   "GeoPackage", "", typename="ave:VerwaltungsEinheit"),
        AdminProduct("alkis", "ALKIS vereinfacht je Kreis (GeoPackage)", KAT, "admin",
                     "GeoPackage (ZIP)", "",
                     description="Vollständige Kreisdatei mit Flurstücken, Gebäuden, Nutzung u. a.",
                     path=g + "lk/akt/gru_vereinfacht_gpkg/", aliases=("alkis-gpkg", "kataster")),
        AdminProduct("alkis-nas", "ALKIS Grundrissdaten je Kreis (NAS)", KAT, "admin",
                     "NAS-XML (ZIP)", "", description="Vollständiges ALKIS im Austauschformat NAS.",
                     path=g + "lk/akt/gru_xml/"),
        AdminProduct("alkis-hist", "ALKIS vereinfacht, Jahresstände (GeoPackage)", KAT, "admin",
                     "GeoPackage (ZIP)", "", yearly=True,
                     description="Jahresstände seit 2016 je Kreis.",
                     path=g + "lk/hist/hist_gru_vereinfacht_gpkg/{year}/"),
        TileProduct("abk", "Amtliche Basiskarte farbig (ABK)", KAT, "tiles", "GeoTIFF", "",
                    description="Großmaßstäbige Karte aus dem Liegenschaftskataster, 1-km-Kacheln.",
                    path=g + "lk/akt/abk_tiff/abk_farbe_tiff/", file_regex=r"\.tif$", raster=True),
        TileProduct("abk-sw", "Amtliche Basiskarte schwarz-weiß (ABK)", KAT, "tiles", "GeoTIFF",
                    "", path=g + "lk/akt/abk_tiff/abk_sw_tiff/", file_regex=r"\.tif$",
                    raster=True),
        SingleProduct("hauskoordinaten", "Gebäudereferenzen / Hauskoordinaten (ASCII)", KAT,
                      "single", "CSV/ASCII (ZIP)", "",
                      description="Adressen mit Koordinate für alle Gebäude in NRW.",
                      path=g + "lk/akt/gebref_txt/", aliases=("gebref", "adressen")),
        # Karten ------------------------------------------------------------------
        TileProduct("dtk25", "Digitale Topographische Karte 1:25 000 (farbig)", KARTE, "tiles",
                    "GeoTIFF", "", path=g + "tk/akt/tk25/dtk25_farbe_tiff/",
                    file_regex=r"\.tif$", raster=True, aliases=("tk25",)),
        TileProduct("dtk50", "Digitale Topographische Karte 1:50 000 (farbig)", KARTE, "tiles",
                    "GeoTIFF", "", path=g + "tk/akt/tk50/dtk50_farbe_tiff/",
                    file_regex=r"\.tif$", raster=True, aliases=("tk50",)),
        TileProduct("dtk100", "Digitale Topographische Karte 1:100 000 (farbig)", KARTE, "tiles",
                    "GeoTIFF", "", path=g + "tk/akt/tk100/dtk100_farbe_tiff/",
                    file_regex=r"\.tif$", raster=True, aliases=("tk100",)),
        TileProduct("dgk5", "Deutsche Grundkarte 1:5 000 (historisch, Grundriss)", KARTE, "tiles",
                    "GeoTIFF", "", path=g + "tk/hist/dgk5/dgk5_gru_tiff/", file_regex=r"\.tif$",
                    raster=True),
        # Landschaftsmodelle ------------------------------------------------------
        SingleProduct("basis-dlm", "Digitales Basis-Landschaftsmodell (Basis-DLM)", LM, "single",
                      "Shape oder NAS (ZIP)", "",
                      description="Topographische Objekte (Straßen, Gewässer, Vegetation ...).",
                      path=g + "lm/akt/basis-dlm/", variants={"shape": "Shape", "nas": "NAS"},
                      default_variant="shape", aliases=("dlm", "atkis")),
        SingleProduct("dlm50", "Digitales Landschaftsmodell 1:50 000 (DLM50)", LM, "single",
                      "Shape oder NAS (ZIP)", "", path=g + "lm/akt/dlm50/",
                      variants={"shape": "Shape", "nas": "NAS"}, default_variant="shape"),
        # Verwaltungsgrenzen ------------------------------------------------------
        SingleProduct("dvg1", "Verwaltungsgrenzen, hohe Stützpunktdichte (DVG1)", VG, "single",
                      "Shape/TIFF/ASCII (ZIP)", "", path=g + "vkg/dvg/dvg1/",
                      variants={"shape": "Shape", "tiff": "TIFF", "ascii": "ASCII"},
                      default_variant="shape", aliases=("verwaltungsgrenzen", "grenzen")),
        SingleProduct("dvg2", "Verwaltungsgrenzen, generalisiert (DVG2)", VG, "single",
                      "Shape/TIFF/ASCII (ZIP)", "", path=g + "vkg/dvg/dvg2/",
                      variants={"shape": "Shape", "tiff": "TIFF", "ascii": "ASCII"},
                      default_variant="shape"),
        # Weitere -----------------------------------------------------------------
        TileProduct("bodenbewegung", "Höhenänderungen aus Sentinel-1 (Bodenbewegung)", SONST,
                    "tiles", "GeoPackage", "16-km-Kacheln",
                    description="Radar-Interferometrie: Hebungen und Senkungen der Oberfläche.",
                    path=g + "bb/bbk_nrw/hoeae_s1/", file_regex=r"\.gpkg$",
                    aliases=("hoeae", "insar", "senkungen")),
        SingleProduct("freizeit", "Touristik- und Freizeitinformationen (TFIS)", SONST, "single",
                      "GeoPackage (ZIP)", "", path=g + "tfis_nrw/", aliases=("tfis",)),
    ]
