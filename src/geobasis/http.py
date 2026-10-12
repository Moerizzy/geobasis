"""Small HTTP layer on top of urllib: retries, a polite User-Agent and an
on-disk cache with ETag/Last-Modified revalidation for catalogue files.

Only catalogue data (index.json, metadata ZIPs, boundaries) is cached here.
Payload downloads are handled by :mod:`geobasis.download`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ._version import __version__

USER_AGENT = f"geobasis/{__version__} (Python; +https://pypi.org/project/geobasis/)"
DEFAULT_TTL = 24 * 3600  # catalogue entries are fresh for one day
TIMEOUT = 120

_memo: dict[str, bytes] = {}
_memo_lock = threading.Lock()


class HTTPError(RuntimeError):
    """Raised when a request fails after all retries."""

    def __init__(self, url: str, msg: str, status: int | None = None):
        super().__init__(f"{msg} ({url})")
        self.url = url
        self.status = status


def cache_dir() -> Path:
    """Platform-specific cache directory (override with GEOBASIS_CACHE)."""
    env = os.environ.get("GEOBASIS_CACHE")
    if env:
        p = Path(env)
    elif sys.platform == "win32":
        p = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "geobasis" / "Cache"
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Caches" / "geobasis"
    else:
        p = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "geobasis"
    return p


def quote_url(url: str) -> str:
    """Percent-encode non-ASCII characters in a URL path (e.g. umlauts)."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%:@!$&'()*+,;=-._~")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def request(url: str, *, data: bytes | None = None, headers: dict | None = None,
            method: str | None = None, timeout: float = TIMEOUT, retries: int = 3):
    """Open a URL with retries on network errors, 429 and 5xx. Returns the
    response object (caller must close it)."""
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    last: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(quote_url(url), data=data, headers=hdrs, method=method)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 304:
                raise
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                last = e
                time.sleep(min(30, 2 ** attempt + float(e.headers.get("Retry-After") or 0)))
                continue
            body = b""
            try:
                body = e.read()[:500]
            except Exception:  # noqa: BLE001
                pass
            raise HTTPError(url, f"HTTP {e.code} {e.reason} {body.decode('utf-8', 'replace')}".strip(),
                            e.code) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
    raise HTTPError(url, f"Netzwerkfehler: {last}")


def _cache_paths(url: str) -> tuple[Path, Path]:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    d = cache_dir() / "http" / h[:2]
    return d / h, d / (h + ".json")


def fetch(url: str, *, ttl: float | None = DEFAULT_TTL, refresh: bool = False) -> bytes:
    """GET ``url`` through the cache. ``ttl=None`` disables caching."""
    if ttl is None:
        with request(url) as r:
            return r.read()
    with _memo_lock:
        if not refresh and url in _memo:
            return _memo[url]
    body_p, meta_p = _cache_paths(url)
    meta: dict = {}
    if body_p.exists() and meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text("utf-8"))
        except ValueError:
            meta = {}
        if meta and not refresh and time.time() - meta.get("fetched", 0) < ttl:
            data = body_p.read_bytes()
            with _memo_lock:
                _memo[url] = data
            return data
    headers = {}
    if meta.get("etag") and body_p.exists():
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified") and body_p.exists():
        headers["If-Modified-Since"] = meta["last_modified"]
    try:
        with request(url, headers=headers) as r:
            data = r.read()
            meta = {"url": url, "etag": r.headers.get("ETag"),
                    "last_modified": r.headers.get("Last-Modified"), "fetched": time.time()}
    except urllib.error.HTTPError as e:
        if e.code != 304:
            raise
        data = body_p.read_bytes()
        meta["fetched"] = time.time()
    except HTTPError:
        if body_p.exists():  # offline or server down: stale cache beats nothing
            print(f"Warnung: {url} nicht erreichbar, verwende Zwischenspeicher.", file=sys.stderr)
            data = body_p.read_bytes()
            with _memo_lock:
                _memo[url] = data
            return data
        raise
    try:
        body_p.parent.mkdir(parents=True, exist_ok=True)
        tmp = body_p.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, body_p)
        meta_p.write_text(json.dumps(meta), "utf-8")
    except OSError:
        pass  # read-only home etc.: caching is an optimisation only
    with _memo_lock:
        _memo[url] = data
    return data


def fetch_json(url: str, **kw):
    return json.loads(fetch(url, **kw))


def clear_cache() -> int:
    """Delete the on-disk cache. Returns the number of removed files."""
    import shutil

    d = cache_dir() / "http"
    n = sum(1 for p in d.rglob("*") if p.is_file()) if d.exists() else 0
    shutil.rmtree(d, ignore_errors=True)
    with _memo_lock:
        _memo.clear()
    return n
