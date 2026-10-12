"""Parallel, resumable downloads with size checks and a manifest.

Layout of the output folder::

    <out>/<product>/[<year>/]<file>
    <out>/<product>/manifest.json      what was downloaded from where, licence
    <out>/<product>/kacheln.geojson    tile outlines for GIS (if known)
    <out>/<product>/<product>.vrt      optional raster mosaic (needs GDAL)
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import http
from ._version import __version__
from .models import RemoteFile, Selection, format_size

CHUNK = 1 << 20


@dataclass
class DownloadResult:
    folder: Path
    files: list[Path] = field(default_factory=list)
    downloaded: int = 0
    skipped: int = 0
    bytes: int = 0
    failed: list[tuple[RemoteFile, str]] = field(default_factory=list)
    manifest: Path | None = None
    footprints: Path | None = None
    vrt: Path | None = None
    extracted: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed

    def summary(self) -> str:
        s = (f"{self.downloaded} geladen, {self.skipped} schon vorhanden, "
             f"{format_size(self.bytes)} übertragen -> {self.folder}")
        if self.failed:
            s += f"; {len(self.failed)} FEHLGESCHLAGEN"
        return s


class _Progress:
    def __init__(self, total_files: int, total_bytes: int, enabled: bool):
        self.total_files, self.total_bytes = total_files, total_bytes
        self.done_files = 0
        self.bytes = 0
        self.enabled = enabled and total_files > 0
        self.lock = threading.Lock()
        self.t0 = time.monotonic()
        self.last = 0.0

    def add(self, n: int) -> None:
        with self.lock:
            self.bytes += n
            self._draw()

    def file_done(self) -> None:
        with self.lock:
            self.done_files += 1
            self._draw(force=True)

    def _draw(self, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and now - self.last < 0.5:
            return
        self.last = now
        rate = self.bytes / max(now - self.t0, 1e-6)
        tot = f" / {format_size(self.total_bytes)}" if self.total_bytes else ""
        sys.stderr.write(f"\r  [{self.done_files}/{self.total_files}] {format_size(self.bytes)}"
                         f"{tot}  {format_size(rate)}/s   ")
        sys.stderr.flush()

    def close(self) -> None:
        if self.enabled:
            sys.stderr.write("\n")


def download_file(f: RemoteFile, target: Path, *, overwrite: bool = False,
                  on_bytes=None) -> tuple[Path, int, bool]:
    """Download one file. Returns (path, bytes transferred, skipped?)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        if f.size is None or target.stat().st_size == f.size:
            return target, 0, True
    part = target.with_name(target.name + ".part")
    start = part.stat().st_size if part.exists() and f.post_data is None else 0
    if f.size is not None and start > f.size:
        start = 0
    headers = {"Range": f"bytes={start}-"} if start else {}
    if f.post_data is not None:
        headers["Content-Type"] = "application/xml"
    transferred = 0
    try:
        resp = http.request(f.url, data=f.post_data, headers=headers, timeout=300)
    except http.HTTPError as e:
        if e.status == 416 and f.size is not None and start == f.size:  # already complete
            os.replace(part, target)
            return target, 0, False
        raise
    except urllib.error.HTTPError as e:  # pragma: no cover - 304 only
        raise http.HTTPError(f.url, f"HTTP {e.code}") from e
    with resp:
        mode = "ab" if start and getattr(resp, "status", 200) == 206 else "wb"
        with open(part, mode) as fh:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                transferred += len(chunk)
                if on_bytes:
                    on_bytes(len(chunk))
    size = part.stat().st_size
    if f.size is not None and size != f.size:
        raise OSError(f"Größe stimmt nicht: {size} statt {f.size} Bytes (erneut versuchen setzt fort)")
    if f.post_data is not None:
        with open(part, "rb") as fh:
            head = fh.read(16)
        if not head.startswith(b"SQLite format 3"):
            text = part.read_text("utf-8", "replace")[:400]
            part.unlink()
            raise OSError(f"WFS lieferte kein GeoPackage: {text}")
    os.replace(part, target)
    return target, transferred, False


def _target(out: Path, f: RemoteFile) -> Path:
    return out / f.subdir / f.name if f.subdir else out / f.name


def download_selection(sel: Selection, out: str | Path = ".", *, workers: int = 4,
                       overwrite: bool = False, progress: bool = True, subdir: bool = True,
                       vrt: bool = False, extract: bool = False,
                       manifest: bool = True) -> DownloadResult:
    """Download all files of a selection into ``out/<product>/``."""
    out = Path(out)
    folder = out / sel.product.id if (subdir and sel.product) else out
    res = DownloadResult(folder=folder)
    if not sel:
        return res
    folder.mkdir(parents=True, exist_ok=True)
    prog = _Progress(len(sel), sel.total_size, progress and sys.stderr.isatty())
    workers = max(1, min(int(workers), 16))

    def job(f: RemoteFile):
        try:
            return f, download_file(f, _target(folder, f), overwrite=overwrite, on_bytes=prog.add), None
        except Exception as e:  # noqa: BLE001 - reported per file
            return f, None, str(e)
        finally:
            prog.file_done()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(job, f) for f in sel]):
            f, r, err = fut.result()
            if err:
                res.failed.append((f, err))
                continue
            path, n, skipped = r
            res.files.append(path)
            res.bytes += n
            if skipped:
                res.skipped += 1
            else:
                res.downloaded += 1
    prog.close()
    res.files.sort()
    if manifest and sel.product:
        res.manifest = _write_manifest(sel, folder, res)
        if any(f.bounds for f in sel):
            res.footprints = _write_footprints(sel, folder)
    if extract:
        res.extracted = _extract_zips([p for p in res.files if p.suffix.lower() == ".zip"])
    if vrt and sel.product is not None and sel.product.raster and res.files:
        years = sorted({f.year for f in sel if f.year and f.subdir})
        suffix = f"_{years[0]}" if len(years) == 1 else ""
        res.vrt = build_vrt([p for p in res.files if p.suffix.lower() in (".tif", ".jp2")],
                            folder / f"{sel.product.id}{suffix}.vrt")
    return res


def _write_manifest(sel: Selection, folder: Path, res: DownloadResult) -> Path:
    p = sel.product
    path = folder / "manifest.json"
    old: dict = {}
    if path.exists():
        try:
            old = json.loads(path.read_text("utf-8"))
        except ValueError:
            old = {}
    entries = {e["name"]: e for e in old.get("dateien", []) if "name" in e}
    ok = {str(x) for x in res.files}
    for f in sel:
        if str(_target(folder, f)) in ok:
            d = f.to_dict()
            d["datei"] = str(_target(folder, f).relative_to(folder))
            entries[f.name] = d
    areas = list(old.get("gebiete", []))
    label = sel.area.label if sel.area else "ganzes Land"
    if label not in areas:
        areas.append(label)
    from .laender import LAENDER

    land = LAENDER.get(p.land)
    doc = {
        "produkt": p.id, "titel": p.title, "land": getattr(land, "name", p.land),
        "quelle": p.source, "lizenz": p.license, "lizenz_url": getattr(land, "license_url", ""),
        "namensnennung_empfohlen": getattr(land, "attribution", ""),
        "gebiete": areas, "aktualisiert": _dt.datetime.now().isoformat(timespec="seconds"),
        "werkzeug": f"geobasis {__version__}", "hinweise": sel.notes,
        "dateien": sorted(entries.values(), key=lambda e: e["name"]),
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    return path


def _write_footprints(sel: Selection, folder: Path) -> Path:
    path = folder / "kacheln.geojson"
    feats: dict[str, dict] = {}
    if path.exists():
        try:
            for ft in json.loads(path.read_text("utf-8")).get("features", []):
                feats[ft["properties"]["name"]] = ft
        except (ValueError, KeyError):
            feats = {}
    for ft in sel.to_geojson()["features"]:
        if ft["geometry"]:
            feats[ft["properties"]["name"]] = ft
    path.write_text(json.dumps({"type": "FeatureCollection", "features": list(feats.values())},
                               ensure_ascii=False), "utf-8")
    return path


def _extract_zips(zips: list[Path]) -> list[Path]:
    out = []
    for z in zips:
        dest = z.with_suffix("")
        with zipfile.ZipFile(z) as zf:
            for m in zf.infolist():  # refuse path traversal
                p = (dest / m.filename).resolve()
                if not str(p).startswith(str(dest.resolve())):
                    raise OSError(f"Unsicherer Pfad in {z.name}: {m.filename}")
            zf.extractall(dest)
        out.append(dest)
    return out


def build_vrt(rasters: list[Path], vrt: Path) -> Path | None:
    """Mosaic as GDAL VRT via ``gdalbuildvrt`` (or the GDAL Python bindings)."""
    if not rasters:
        return None
    exe = shutil.which("gdalbuildvrt")
    if exe:
        lst = vrt.with_suffix(".txt")
        lst.write_text("\n".join(str(p.resolve()) for p in rasters), "utf-8")
        subprocess.run([exe, "-q", "-overwrite", "-input_file_list", str(lst), str(vrt)], check=True)
        lst.unlink()
        return vrt
    try:
        from osgeo import gdal  # type: ignore[import-not-found]
    except ImportError:
        print("Hinweis: Für --vrt wird GDAL benötigt (gdalbuildvrt nicht gefunden).", file=sys.stderr)
        return None
    gdal.BuildVRT(str(vrt), [str(p) for p in rasters])
    return vrt
