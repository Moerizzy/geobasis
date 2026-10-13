"""A tiny stand-in for opengeodata.nrw.de and the NRW WFS services.

It serves a generated folder tree with index.json files, metadata ZIPs and
small dummy payloads (with HTTP Range support), plus canned WFS answers.
"""

from __future__ import annotations

import io
import json
import re
import threading
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from geobasis.geo import transformer

TS = "2025-01-01T00:00:00"


def square(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


# administrative units (EPSG:25832), loosely around Münster
UNITS = {
    "gem": [
        ("Münster", "05515000", square(400000, 5750000, 402000, 5752000)),
        ("Telgte", "05570044", square(402000, 5750000, 404000, 5752000)),
        ("Bad Münstereifel", "05366004", square(340000, 5600000, 342000, 5602000)),
        ("Bad Honnef", "05382008", square(372000, 5608000, 374000, 5612000)),
    ],
    "krs": [
        ("Münster", "05515000", square(400000, 5750000, 402000, 5752000)),
        ("Warendorf", "05570000", square(402000, 5748000, 406000, 5754000)),
        ("Euskirchen", "05366000", square(330000, 5590000, 350000, 5610000)),
        ("Rhein-Sieg-Kreis", "05382000", square(360000, 5600000, 390000, 5630000)),
    ],
    "rbz": [
        ("Münster", "05500000", square(398000, 5746000, 408000, 5756000)),
        ("Köln", "05300000", square(320000, 5580000, 400000, 5650000)),
    ],
}

# Niedersachsen (VG250/VG25 style: lower-case fields, 5-digit district keys)
UNITS_NI = {
    "gem": [
        ("Osnabrück", "03404000", "Stadt", square(430000, 5788000, 432000, 5790000)),
        ("Wallenhorst", "03459033", "Gemeinde", square(430000, 5790000, 432000, 5792000)),
        ("Munster", "03358016", "Stadt", square(560000, 5870000, 562000, 5872000)),
    ],
    "krs": [
        ("Osnabrück", "03404", "Kreisfreie Stadt", square(430000, 5788000, 432000, 5790000)),
        ("Osnabrück", "03459", "Landkreis", square(420000, 5770000, 446000, 5800000)),
        ("Heidekreis", "03358", "Landkreis", square(540000, 5850000, 580000, 5890000)),
    ],
}


def _ni_items():
    """STAC items for the fake LGLN catalogues: {service: [(collection, item)]}."""
    to_ll = transformer(25832, 4326)

    def item(iid, e, n, size_km, date, assets):
        x0, y0, x1, y1 = e * 1000, n * 1000, (e + size_km) * 1000, (n + size_km) * 1000
        (a, b), (c, d) = to_ll(x0, y0), to_ll(x1, y1)
        return {"type": "Feature", "id": iid, "bbox": [a, b, c, d],
                "geometry": square(a, b, c, d),
                "properties": {"datetime": f"{date}T00:00:00Z", "bildflugname": "Test"},
                "assets": assets}

    out = {"dgm": [], "dop": []}
    for e in (430, 431):
        for n in (5788, 5789):
            for year, date in ((2017, "2017-03-13"), (2023, "2023-06-04")):
                iid = f"dgm1_32_{e}_{n}_1_ni_{year}"
                out["dgm"].append(("dgm1", item(iid, e, n, 1, date, {
                    "dgm1-tif": {"href": f"/files/ni/{iid}.tif", "roles": ["data"]},
                    "dgm1-metadata": {"href": f"/files/ni/{iid}.xml", "roles": ["metadata"]}})))
    for date in ("2014-04-16", "2020-03-26", "2025-03-03"):
        iid = f"dop20rgbi_32_430_5788_2_ni_{date}"
        out["dop"].append(("DOP", item(iid, 430, 5788, 2, date, {
            "dop20_rgb": {"href": f"/files/ni/{iid.replace('rgbi', 'rgb')}.tif", "roles": ["data"]},
            "dop20_rgbi": {"href": f"/files/ni/{iid}.tif", "roles": ["data"]}})))
    for e in (430, 431):
        for n in (5788, 5789):
            iid = f"dop10rgbi_32_{e}_{n}_1_ni_2025-03-03"
            out["dop"].append(("DOP", item(iid, e, n, 1, "2025-03-03", {
                "dop20_rgb": {"href": f"/files/ni/{iid.replace('rgbi', 'rgb')}.tif", "roles": ["data"]},
                "dop20_rgbi": {"href": f"/files/ni/{iid}.tif", "roles": ["data"]}})))
    return out


NI_ITEMS = _ni_items()
NI_EXTENT = {"dgm": ["2017-03-13T00:00:00+00:00", "2023-06-04T00:00:00+00:00"],
             "dop": ["2014-04-16T00:00:00+00:00", "2025-03-03T00:00:00+00:00"]}


def _payload(name: str, n: int) -> bytes:
    return (name.encode() * (n // max(len(name), 1) + 1))[:n]


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for k, v in members.items():
            zf.writestr(k, v)
    return buf.getvalue()


class Tree:
    """Builds the produkte/ folder tree under ``root``."""

    def __init__(self, root: Path):
        self.root = root / "produkte"

    def folder(self, path: str, folders=(), datasets=(), metafiles=()):
        d = self.root / path
        d.mkdir(parents=True, exist_ok=True)
        idx = {"folders": [{"name": f, "title": f, "timestamp": TS} for f in folders]}
        if metafiles:
            idx["metafiles"] = []
        for name, data in metafiles:
            (d / name).write_bytes(data)
            idx["metafiles"].append({"name": name, "size": str(len(data)), "timestamp": TS})
        if datasets:
            idx["datasets"] = []
        for ds_name, files in datasets:
            entry = {"name": ds_name, "title": ds_name, "files": []}
            for fname, data, claimed in files:
                (d / fname).write_bytes(data)
                entry["files"].append({"name": fname, "size": str(claimed or len(data)),
                                       "timestamp": TS})
            idx["datasets"].append(entry)
        (d / "index.json").write_text(json.dumps(idx), "utf-8")

    def build(self):
        # DGM1: 4 x 3 tiles + an older duplicate
        files = []
        rows = []
        for e in range(400, 404):
            for n in range(5750, 5753):
                name = f"dgm1_32_{e}_{n}_1_nw_2024.tif"
                files.append((name, _payload(name, 1000 + e - 400), None))
                rows.append(f"{name[:-4]};2024-03-{e - 390:02d};5020;2024-03-20")
        old = "dgm1_32_400_5750_1_nw_2021.tif"
        files.append((old, _payload(old, 900), None))
        csv = ("Kachelinformationen des DGM1 fuer die Datenabgabe\nLand;Nordrhein-Westfalen\n"
               "Kachelname;Aktualitaet;Erfassungsmethode;Fortfuehrung\n" + "\n".join(rows) + "\n")
        self.folder("geobasis/hm/dgm1_tiff/dgm1_tiff/", datasets=[("dgm1_tiff_kacheln", files)],
                    metafiles=[("dgm1_meta.zip", _zip_bytes({"dgm1_nw.csv": csv.encode()}))])
        # a product whose index lies about a size (for the size check)
        self.folder("geobasis/hm/dom1_tiff/dom1_tiff/", datasets=[("dom1", [
            ("dom1_32_400_5750_1_nw_2024.tif", b"x" * 100, 200)])])
        # ALKIS per district (current and yearly)
        kreis_files = [(f"gru_vereinf_{ags}_{name}_EPSG25832_GeoPackage.zip",
                        _zip_bytes({f"{name}.gpkg": b"SQLite format 3\x00" + b"0" * 50}), None)
                       for name, ags, _ in UNITS["krs"]]
        self.folder("geobasis/lk/akt/gru_vereinfacht_gpkg/",
                    datasets=[("gru_vereinfacht_gpkg", kreis_files)])
        self.folder("geobasis/lk/hist/hist_gru_vereinfacht_gpkg/", folders=["2016", "2017"])
        for y in ("2016", "2017"):
            self.folder(f"geobasis/lk/hist/hist_gru_vereinfacht_gpkg/{y}/", datasets=[
                ("hist", [(f"{y}_{n}", d, c) for n, d, c in kreis_files])])
        # land cover per administrative region
        self.folder("geobasis/lusat/akt/lb_nrw/", datasets=[("lb_nrw", [
            ("lb_nrw_05500000_Münster_EPSG25832_GeoPackage.zip", b"PK" + b"0" * 30, None),
            ("lb_nrw_05300000_Köln_EPSG25832_GeoPackage.zip", b"PK" + b"0" * 40, None)])])
        # single files with format variants
        self.folder("geobasis/lm/akt/basis-dlm/", datasets=[
            ("basis-dlm_NAS", [("basis-dlm_EPSG25832_NAS.zip", b"n" * 10, None)]),
            ("basis-dlm_Shape", [("basis-dlm_EPSG25832_Shape.zip", b"s" * 20, None)])])
        # historic orthophotos: 1952 in both GK strips, 2015 in UTM
        root = "geobasis/lusat/hist/hist_dop/hist_dop_jp2_f10/"
        self.folder(root, folders=["hist_dop_1952", "hist_dop_2015"])
        self.folder(root + "hist_dop_1952/", folders=["epsg_31466", "epsg_31467"])
        for code in (31466, 31467):
            fn = transformer(25832, code)
            xs, ys = zip(*[fn(x, y) for x in (399000, 405000) for y in (5749000, 5753000)])
            hist_files, meta = [], ["RECHTS;HOCH;BEZEICHNER;JAHRDATEI;EPSG;FLUGDATUM;GSD;KANAELE"]
            for gx in range(int(min(xs) // 2000) * 2, int(max(xs) // 2000) * 2 + 2, 2):
                for gy in range(int(min(ys) // 2000) * 2, int(max(ys) // 2000) * 2 + 2, 2):
                    name = f"dop40pan_{gx}_{gy}_2_nw_1952.jp2"
                    hist_files.append((name, _payload(name, 300), None))
                    meta.append(f"{gx}000.000;{gy}000.000;x;1952/{name};EPSG:{code};1952-05-0{code % 10};0.4;PAN")
            self.folder(f"{root}hist_dop_1952/epsg_{code}/", datasets=[("hist", hist_files)],
                        metafiles=[("dop_meta.zip", _zip_bytes({"dop1952_meta.csv": "\n".join(meta).encode()}))])
        ni_dir = self.root.parent / "files" / "ni"
        ni_dir.mkdir(parents=True, exist_ok=True)
        for items in NI_ITEMS.values():
            for _, it in items:
                for a in it["assets"].values():
                    name = a["href"].rsplit("/", 1)[1]
                    size = 400 if "rgbi" in name else 100
                    (ni_dir / name).write_bytes(_payload(name, size))
        self.folder(root + "hist_dop_2015/", folders=["epsg_25832"])
        self.folder(root + "hist_dop_2015/epsg_25832/", datasets=[("hist", [
            (f"dop10rgbi_32{e}_{n}_1_nw_2015.jp2", b"j" * 50, None)
            for e in (400, 401) for n in (5750, 5751)])])


class Handler(BaseHTTPRequestHandler):
    root: Path
    wfs_hits = 3

    def log_message(self, *a):  # keep test output quiet
        pass

    def do_HEAD(self):
        p = self.root / urllib.parse.unquote(urllib.parse.urlsplit(self.path).path).lstrip("/")
        if not p.is_file():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(p.stat().st_size))
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path == "/dvg":
            return self._dvg(urllib.parse.parse_qs(u.query))
        if u.path in ("/vg250", "/vg25"):
            return self._vg(urllib.parse.parse_qs(u.query))
        if u.path.startswith("/stac/"):
            return self._stac(u.path, urllib.parse.parse_qs(u.query))
        rel = urllib.parse.unquote(u.path).lstrip("/")
        p = self.root / rel
        if p.is_dir():
            p = p / "index.json"
        if not p.is_file():
            self.send_error(404)
            return
        data = p.read_bytes()
        rng = self.headers.get("Range")
        if rng:
            start = int(re.match(r"bytes=(\d+)-", rng).group(1))
            if start >= len(data):
                self.send_response(416)
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
            data = data[start:]
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("ETag", '"x"')
        self.end_headers()
        self.wfile.write(data)

    def _dvg(self, q):
        typename = q["TYPENAMES"][0].split(":")[1]  # nw_dvg2_gem
        level = typename.rsplit("_", 1)[1]
        units = UNITS[level]
        flt = q.get("FILTER", [""])[0]
        m = re.search(r"<fes:Literal>(\d+)</fes:Literal>", flt)
        if m:
            units = [u for u in units if u[1] == m.group(1)]
        fc = {"type": "FeatureCollection",
              "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25832"}},
              "features": [{"type": "Feature", "properties": {"GN": n, "KN": k}, "geometry": g}
                           for n, k, g in units]}
        self._send(json.dumps(fc).encode(), "application/json")

    def _vg(self, q):
        typename = q["TYPENAMES"][0].split(":")[1]  # vg250_gem / vg25_krs
        units = UNITS_NI[typename.rsplit("_", 1)[1]]
        flt = q.get("FILTER", [""])[0]
        field = re.search(r"<fes:ValueReference>(\w+)</fes:ValueReference>", flt).group(1)
        value = re.search(r"<fes:Literal>(\w+)</fes:Literal>", flt).group(1)
        if field == "ags":
            units = [u for u in units if u[1] == value]
        elif field == "sn_l" and value != "03":
            units = []
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": g,
             "properties": {"gen": n, "ags": k, "bez": b, "sn_l": "03", "gf": 4}}
            for n, k, b, g in units]}
        self._send(json.dumps(fc).encode(), "application/json")

    def _stac(self, path, q):
        parts = path.strip("/").split("/")  # stac/<svc>/collections/<coll>[/items]
        svc, coll = parts[1], parts[3]
        if len(parts) == 4:
            doc = {"id": coll, "extent": {"temporal": {"interval": [NI_EXTENT[svc]]}}}
            return self._send(json.dumps(doc).encode(), "application/json")
        items = [it for c, it in NI_ITEMS[svc] if c == coll]
        if "bbox" in q:
            x0, y0, x1, y1 = map(float, q["bbox"][0].split(","))
            items = [it for it in items if not (it["bbox"][0] > x1 or it["bbox"][2] < x0
                                                or it["bbox"][1] > y1 or it["bbox"][3] < y0)]
        if "datetime" in q:
            start, end = q["datetime"][0].split("/")
            items = [it for it in items if start[:10] <= it["properties"]["datetime"][:10] <= end[:10]]
        limit = int(q.get("limit", ["10"])[0])
        start = int(q.get("token", ["0"])[0])
        base = f"http://{self.headers['Host']}"
        page = []
        for it in items[start:start + limit]:
            it = json.loads(json.dumps(it))
            for a in it["assets"].values():
                a["href"] = base + a["href"]
            page.append(it)
        links = []
        if start + limit < len(items):
            nq = dict((k, v[0]) for k, v in q.items())
            nq["token"] = str(start + limit)
            links.append({"rel": "next", "href": f"{base}{path}?{urllib.parse.urlencode(nq)}"})
        doc = {"type": "FeatureCollection", "features": page, "links": links}
        self._send(json.dumps(doc).encode(), "application/json")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        if 'resultType="hits"' in body:
            out = f'<wfs:FeatureCollection numberMatched="{self.wfs_hits}" numberReturned="0"/>'
            return self._send(out.encode(), "text/xml")
        if "ave:Broken" in body:
            return self._send(b"<ows:ExceptionReport>kaputt</ows:ExceptionReport>", "text/xml")
        self._send(b"SQLite format 3\x00" + b"\x00" * 100, "application/geopackage+sqlite3")

    def _send(self, data: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FakeServer:
    def __init__(self, root: Path):
        Tree(root).build()
        handler = type("H", (Handler,), {"root": root})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
