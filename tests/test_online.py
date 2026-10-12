"""Checks against the real services. Run with: pytest -m online"""

import pytest

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
