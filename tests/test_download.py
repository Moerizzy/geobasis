import json

import pytest

from geobasis import nrw
from geobasis.download import download_selection
from geobasis.models import RemoteFile, Selection


def test_download_and_manifest(fake, tmp_path):
    sel = nrw.find("dgm1", gemeinde="Münster")
    res = sel.download(tmp_path, progress=False)
    assert res.ok and res.downloaded == len(sel) and res.skipped == 0
    folder = tmp_path / "dgm1"
    for f in sel:
        assert (folder / f.name).stat().st_size == f.size
    man = json.loads((folder / "manifest.json").read_text("utf-8"))
    assert man["produkt"] == "dgm1" and man["lizenz"].startswith("Datenlizenz")
    assert len(man["dateien"]) == len(sel)
    assert man["gebiete"] == ["Gemeinde Münster (05515000)"]
    fc = json.loads((folder / "kacheln.geojson").read_text("utf-8"))
    assert len(fc["features"]) == len(sel)
    lon, lat = fc["features"][0]["geometry"]["coordinates"][0][0]
    assert 7 < lon < 8 and 51 < lat < 52
    # second run: everything is skipped, manifest accumulates areas
    res2 = sel.download(tmp_path, progress=False)
    assert res2.skipped == len(sel) and res2.downloaded == 0
    nrw.find("dgm1", gemeinde="Telgte").download(tmp_path, progress=False)
    man = json.loads((folder / "manifest.json").read_text("utf-8"))
    assert len(man["gebiete"]) == 2


def test_resume_partial_file(fake, tmp_path):
    sel = nrw.find("dgm1", point=(400500, 5751500))
    f = sel[0]
    folder = tmp_path / "dgm1"
    folder.mkdir()
    full = sel.download(tmp_path / "ref", progress=False).files[0].read_bytes()
    (folder / (f.name + ".part")).write_bytes(full[:300])
    res = sel.download(tmp_path, progress=False)
    assert res.ok and res.bytes == len(full) - 300
    assert (folder / f.name).read_bytes() == full
    assert not (folder / (f.name + ".part")).exists()


def test_size_mismatch_is_reported(fake, tmp_path):
    sel = nrw.find("dom1", point=(400500, 5750500))
    res = sel.download(tmp_path, progress=False)
    assert not res.ok and "Größe" in res.failed[0][1]


def test_wfs_download_and_error(fake, tmp_path):
    sel = nrw.find("gebaeude", gemeinde="Münster")
    res = sel.download(tmp_path, progress=False)
    assert res.ok
    assert res.files[0].read_bytes().startswith(b"SQLite format 3")
    bad = Selection([RemoteFile(name="x.gpkg", url=fake.url + "/wfs", post_data=b"ave:Broken")])
    res = download_selection(bad, tmp_path, progress=False)
    assert not res.ok and "kein GeoPackage" in res.failed[0][1]


def test_extract_zip(fake, tmp_path):
    res = nrw.find("alkis", kreis="Münster").download(tmp_path, progress=False, extract=True)
    assert res.extracted and (res.extracted[0] / "Münster.gpkg").exists()


def test_hist_download_goes_to_year_folder(fake, tmp_path):
    res = nrw.find("dop-hist", year=2015, point=(400500, 5750500)).download(tmp_path, progress=False)
    assert res.files[0].parent == tmp_path / "dop-hist" / "2015"


def test_empty_selection_creates_nothing(tmp_path):
    res = download_selection(Selection([], None), tmp_path / "leer", progress=False)
    assert res.ok and not (tmp_path / "leer").exists()


@pytest.mark.parametrize("workers", [1, 8])
def test_parallel_workers(fake, tmp_path, workers):
    res = nrw.find("dgm1", with_meta=False).download(tmp_path, workers=workers, progress=False)
    assert res.ok and res.downloaded == 12
