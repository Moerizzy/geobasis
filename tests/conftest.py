import pytest

from geobasis import http
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
    grenzen._units_cache.clear()
    grenzen._geom_cache.clear()


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
    """Point the NRW module at the local fake portal."""
    monkeypatch.setattr(portal, "BASE", server.url + "/produkte/")
    monkeypatch.setattr(grenzen, "WFS", server.url + "/dvg")
    monkeypatch.setattr(wfs, "ALKIS_WFS", server.url + "/wfs")
    return server
