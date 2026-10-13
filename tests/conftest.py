import pytest

from geobasis import grenzen as boundaries
from geobasis import http
from geobasis.laender.ni import grenzen as ni_grenzen
from geobasis.laender.ni import stac
from geobasis.laender.nrw import grenzen, portal, wfs

from .fakeportal import FakeServer


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    s = FakeServer(tmp_path_factory.mktemp("portal"))
    yield s
    s.close()


@pytest.fixture(scope="session")
def online_cache(tmp_path_factory):
    return tmp_path_factory.mktemp("online-cache")


def _reset():
    http._memo.clear()
    boundaries.clear_caches()


@pytest.fixture(autouse=True)
def _isolated_cache(request, tmp_path, monkeypatch):
    if request.node.get_closest_marker("online"):
        cache = request.getfixturevalue("online_cache")
    else:
        cache = tmp_path / "cache"
    monkeypatch.setenv("GEOBASIS_CACHE", str(cache))
    _reset()
    yield
    _reset()


@pytest.fixture
def fake(server, monkeypatch):
    """Point the NRW and NI modules at the local fake services."""
    monkeypatch.setattr(portal, "BASE", server.url + "/produkte/")
    monkeypatch.setattr(grenzen, "WFS", server.url + "/dvg")
    monkeypatch.setattr(wfs, "ALKIS_WFS", server.url + "/wfs")
    monkeypatch.setattr(ni_grenzen, "VG250_WFS", server.url + "/vg250")
    monkeypatch.setattr(ni_grenzen, "VG25_WFS", server.url + "/vg25")
    for svc in ("dgm", "dom", "bdom", "dop"):
        monkeypatch.setitem(stac.ENDPOINTS, svc, f"{server.url}/stac/{svc}")
    monkeypatch.setattr(stac, "PAGE", 3)  # force paging in tests
    return server
