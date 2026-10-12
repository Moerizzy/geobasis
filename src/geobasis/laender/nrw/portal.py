"""Client for the open data portal https://www.opengeodata.nrw.de/produkte/.

The portal is a tree of folders; every folder serves an ``index.json``
listing sub-folders, datasets (each with files) and accompanying
"metafiles". Tiled products ship a ``*_meta.zip`` with a CSV that gives the
exact acquisition date (and more) for every tile.
"""

from __future__ import annotations

import csv
import io
import posixpath
import zipfile
from dataclasses import dataclass, field

from ... import http
from ...tiles import parse_tile

BASE = "https://www.opengeodata.nrw.de/produkte/"


def url_for(path: str) -> str:
    if path.startswith("http"):
        return path
    return BASE + path.lstrip("/")


def _folder(path: str) -> str:
    path = path.strip("/")
    return path + "/" if path else ""


@dataclass
class PortalFile:
    name: str
    url: str
    size: int | None
    timestamp: str | None
    dataset: str = ""
    dataset_title: str = ""


@dataclass
class Listing:
    path: str
    folders: list[dict] = field(default_factory=list)
    files: list[PortalFile] = field(default_factory=list)
    metafiles: list[PortalFile] = field(default_factory=list)


def index(path: str, refresh: bool = False) -> dict:
    """Raw ``index.json`` of a portal folder (cached for a day)."""
    return http.fetch_json(url_for(_folder(path) + "index.json"), refresh=refresh)


def listing(path: str, refresh: bool = False) -> Listing:
    """Parsed content of a portal folder."""
    folder = _folder(path)
    d = index(folder, refresh=refresh)
    base = url_for(folder)
    out = Listing(path=folder, folders=list(d.get("folders") or []))
    for ds in d.get("datasets") or []:
        for f in ds.get("files") or []:
            out.files.append(PortalFile(
                name=f["name"], url=base + f["name"], size=_int(f.get("size")),
                timestamp=f.get("timestamp"), dataset=ds.get("name", ""),
                dataset_title=ds.get("title", "")))
    for m in d.get("metafiles") or []:
        out.metafiles.append(PortalFile(name=m["name"], url=base + m["name"],
                                        size=_int(m.get("size")), timestamp=m.get("timestamp")))
    return out


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Per-tile metadata
# --------------------------------------------------------------------------

_HEADER_FIRST = {"kachelname", "nummer", "rechts"}
DATE_COLUMNS = ("Aktualitaet", "Aufnahmedatum_bDOM", "FLUGDATUM", "Spitzenaktualität",
                "Topographie", "Fortfuehrung")


class MetaTable:
    """Rows of a tile metadata CSV, addressable by tile name or grid key."""

    def __init__(self, rows: list[dict[str, str]], key_column: str, crs: int | None = None):
        self.rows = rows
        self.by_name: dict[str, dict[str, str]] = {}
        self.by_key: dict[str, list[dict[str, str]]] = {}
        for r in rows:
            raw = (r.get(key_column) or "").strip()
            if not raw:
                continue
            stem = posixpath.splitext(posixpath.basename(raw.replace("\\", "/")))[0]
            self.by_name[stem] = r
            ref = parse_tile(stem, crs)
            if ref:
                self.by_key.setdefault(ref.key, []).append(r)

    def __len__(self) -> int:
        return len(self.rows)

    def lookup(self, name: str, key: str | None = None) -> dict[str, str] | None:
        stem = posixpath.splitext(name)[0]
        row = self.by_name.get(stem)
        if row is None and key is not None:
            cands = self.by_key.get(key) or []
            if len(cands) == 1:
                row = cands[0]
        return row

    @staticmethod
    def date_of(row: dict[str, str], preferred: str | None = None) -> str | None:
        cols = ((preferred,) if preferred else ()) + DATE_COLUMNS
        for c in cols:
            v = (row.get(c) or "").strip()
            if v:
                return v.replace("-00-00", "").replace("-00", "")
        return None


def parse_meta_csv(text: str, crs: int | None = None) -> MetaTable | None:
    lines = text.splitlines()
    head = None
    for i, line in enumerate(lines):
        cols = [c.strip() for c in line.split(";")]
        if cols and (cols[0].lower() in _HEADER_FIRST or "JAHRDATEI" in cols or "LOCATION" in cols):
            head = i
            break
    if head is None:
        return None
    reader = csv.DictReader(io.StringIO("\n".join(lines[head:])), delimiter=";")
    fields = [f.strip() for f in (reader.fieldnames or [])]
    reader.fieldnames = fields
    rows = [{k: (v or "").strip() for k, v in r.items() if k} for r in reader]
    key_col = next((c for c in ("Kachelname", "JAHRDATEI", "LOCATION", "Nummer") if c in fields),
                   fields[0])
    if key_col == "RECHTS":  # pragma: no cover - defensive
        return None
    return MetaTable(rows, key_col, crs)


def load_meta(url: str, crs: int | None = None) -> MetaTable | None:
    """Download (cached) and parse a ``*_meta.zip``; ``None`` if unusable."""
    try:
        raw = http.fetch(url)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not names:
                return None
            data = zf.read(names[0])
    except (zipfile.BadZipFile, http.HTTPError, OSError):
        return None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover
        text = data.decode("utf-8", "replace")
    return parse_meta_csv(text, crs)
