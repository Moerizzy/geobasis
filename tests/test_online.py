"""Checks against the real services. Run with: pytest -m online"""

import pytest

from geobasis import ni as ni_land
from geobasis import nrw
from geobasis.laender.nrw import portal

pytestmark = pytest.mark.online


@pytest.mark.parametrize("pid", [p.id for p in nrw.products() if p.kind in ("tiles", "admin", "single")
                                 and not p.yearly])
def test_every_product_has_files(pid):
    sel = nrw.find(pid, with_meta=False)
    assert len(sel) > 0, pid
    assert sel.total_size > 0


@pytest.mark.parametrize("pid", [p.id for p in nrw.products() if p.yearly])
def test_archives_have_years(pid):
    years = nrw.product(pid).years()
    assert years and years[-1] >= 2024


def test_tiles_have_dates():
    sel = nrw.find("dgm1", gemeinde="Münster")
    assert 300 < len(sel) < 450
    assert all(f.date for f in sel)


def test_wfs_counts():
    sel = nrw.find("flurstuecke", point=(7.6261, 51.9625), radius=100)
    assert sel and sel[0].meta["objekte"] > 10


def test_hist_point_coverage():
    sel = nrw.find("dop-hist", year=1954, point=(7.6261, 51.9625))
    assert len(sel) == 1 and sel[0].crs == 31467


def test_portal_root():
    names = [f["name"] for f in portal.listing("").folders]
    assert "geobasis" in names


@pytest.mark.parametrize("pid", [p.id for p in ni_land.products() if not p.yearly])
def test_ni_products_have_files(pid):
    sel = ni_land.find(pid, point=(8.0472, 52.2799), radius=1500, with_meta=False)
    if pid == "dop10" and not sel:
        pytest.skip("DOP10 noch nicht flächendeckend")
    assert sel, pid
    assert all(f.url.startswith("https://") for f in sel)


def test_ni_archive_years():
    cov = ni_land.product("dop-hist").coverage(ni_land.area(point=(8.0472, 52.2799)))
    assert sum(1 for n in cov.values() if n) >= 3


def test_ni_boundaries():
    import geobasis

    a, lands = geobasis.area(gemeinde="Wallenhorst")
    assert a.ags == "03459033" and lands[0].code == "ni"
    with pytest.raises(LookupError, match="mehrdeutig"):
        geobasis.area(kreis="Osnabrück")


def test_cross_border():
    import geobasis

    sel = geobasis.find("dgm1", bbox=(7.95, 52.15, 8.0, 52.19), with_meta=False)
    assert {f.land for f in sel} == {"nw", "ni"}
