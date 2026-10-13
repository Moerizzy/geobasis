import json

import pytest

import geobasis
from geobasis import ni


def keys(sel):
    return sorted(f.key for f in sel)


def test_ni_catalogue():
    ids = [p.id for p in ni.products()]
    assert {"dgm1", "dom1", "bdom20", "dop20", "dop10", "dop-hist"} <= set(ids)
    for p in ni.products():
        assert p.land == "ni" and "CC BY 4.0" in p.license and not p.enumerable


def test_ni_tiles_latest_and_all_versions(fake):
    sel = ni.find("dgm1", gemeinde="Osnabrück")  # uses paging (page size 3)
    assert keys(sel) == ["430_5788", "430_5789", "431_5788", "431_5789"]
    assert {f.year for f in sel} == {2023} and {f.date for f in sel} == {"2023-06-04"}
    assert all(f.size == 100 for f in sel)  # sizes from HEAD requests
    assert all(f.land == "ni" and f.url.startswith(fake.url) for f in sel)
    assert len(ni.find("dgm1", gemeinde="Osnabrück", latest=False)) == 8
    assert sel.area.label == "Stadt Osnabrück (03404000)"


def test_ni_dop_variants(fake):
    sel = ni.find("dop", point=(430500, 5788500))
    assert [f.name for f in sel] == ["dop20rgb_32_430_5788_2_ni_2025-03-03.tif"]
    rgbi = ni.find("dop20", point=(430500, 5788500), variant="rgbi")
    assert rgbi[0].name.startswith("dop20rgbi") and rgbi[0].size == 400
    assert keys(ni.find("dop10", bbox=(430000, 5788000, 432000, 5790000))) == [
        "430_5788", "430_5789", "431_5788", "431_5789"]


def test_ni_archive(fake):
    p = ni.product("dop-hist")
    assert p.years() == list(range(2014, 2026))
    sel = ni.find("dop-hist", year=2020, point=(430500, 5788500))
    assert [f.date for f in sel] == ["2020-03-26"] and sel[0].subdir == "2020"
    cov = p.coverage(geobasis.Area.from_point((430500, 5788500)))
    assert {y for y, n in cov.items() if n} == {2014, 2020, 2025}


def test_ni_district_names(fake):
    with pytest.raises(LookupError, match="mehrdeutig"):
        geobasis.area(kreis="Osnabrück")
    a, lands = geobasis.area(kreis="Landkreis Osnabrück")
    assert a.ags == "03459000" and [lnd.code for lnd in lands] == ["ni"]
    assert geobasis.area(kreis="03404")[0].label == "Kreisfreie Stadt Osnabrück (03404000)"


def test_names_across_states(fake):
    assert geobasis.area(gemeinde="Münster")[1][0].code == "nw"
    assert geobasis.area(gemeinde="Munster")[1][0].code == "ni"
    assert geobasis.area(gemeinde="05515000")[1][0].code == "nw"


def test_cross_border_query_and_download(fake, tmp_path):
    sel = geobasis.find("dgm1", bbox=(400000, 5750000, 432000, 5790000))
    assert sorted({f.land for f in sel}) == ["ni", "nw"]
    assert sum(f.land == "nw" for f in sel) == 12 and sum(f.land == "ni" for f in sel) == 4
    assert "(NI 4, NW 12)" in sel.summary()
    res = sel.download(tmp_path, progress=False)
    assert res.ok and res.downloaded == 16
    man = json.loads((tmp_path / "dgm1" / "manifest.json").read_text("utf-8"))
    assert {q["land"] for q in man["quellen"]} == {"Nordrhein-Westfalen", "Niedersachsen"}
    assert {f["land"] for f in man["dateien"]} == {"nw", "ni"}


def test_routing_skips_states_without_hits(fake):
    sel = geobasis.find("dgm1", point=(430500, 5788500))
    assert {f.land for f in sel} == {"ni"} and len(sel.products) == 1


def test_product_only_in_one_state(fake):
    assert geobasis.find("flurstuecke", gemeinde="Münster")[0].land == "nw"
    with pytest.raises(KeyError, match="gibt es für NI nicht"):
        geobasis.find("flurstuecke", land="ni", point=(430500, 5788500))
