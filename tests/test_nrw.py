import json

import pytest

from geobasis import Area, nrw
from geobasis.laender.nrw import grenzen


def keys(sel):
    return sorted(f.key for f in sel)


def test_catalogue_is_consistent():
    ids = [p.id for p in nrw.products()]
    assert len(ids) == len(set(ids))
    aliases = [a for p in nrw.products() for a in p.aliases]
    assert not set(aliases) & set(ids)
    assert len(aliases) == len(set(aliases))
    for p in nrw.products():
        assert p.kind in {"tiles", "admin", "single", "wfs"}
        assert p.license.startswith("Datenlizenz Deutschland")
        assert p.source.startswith("https://")
        assert p.info()["id"] == p.id


def test_product_lookup():
    assert nrw.product("DGM").id == "dgm1"
    assert nrw.product("luftbild").id == "dop10"
    with pytest.raises(KeyError, match="dgm1"):
        nrw.product("dgm2")


def test_tiles_by_gemeinde(fake):
    sel = nrw.find("dgm1", gemeinde="Münster")
    # Münster is exactly tiles 400-401 x 5750-5751; neighbours only touch it
    assert keys(sel) == ["400_5750", "400_5751", "401_5750", "401_5751"]
    assert sel.area.ags == "05515000"
    f = next(f for f in sel if f.key == "400_5750")
    assert f.year == 2024  # newest of two versions
    assert f.date == "2024-03-10"
    assert f.meta["Fortfuehrung"] == "2024-03-20"
    assert f.bounds == (400000.0, 5750000.0, 401000.0, 5751000.0)
    assert "Gemeinde Münster" in sel.summary()


def test_grid_aligned_bbox_selects_only_covered_tiles(fake):
    sel = nrw.find("dgm1", bbox=(400000, 5750000, 402000, 5751000))
    assert keys(sel) == ["400_5750", "401_5750"]


def test_tiles_all_versions(fake):
    sel = nrw.find("dgm1", bbox=(400100, 5750100, 400200, 5750200), latest=False)
    assert sorted(f.name for f in sel) == ["dgm1_32_400_5750_1_nw_2021.tif",
                                          "dgm1_32_400_5750_1_nw_2024.tif"]


def test_tiles_by_point_and_lonlat_bbox(fake):
    sel = nrw.find("dgm1", point=(402500, 5751500), radius=0)
    assert keys(sel) == ["402_5751"]
    sel = nrw.find("dgm1", point=(402500, 5751500), radius=600)
    assert keys(sel) == ["401_5751", "402_5750", "402_5751", "402_5752", "403_5751"]
    lonlat = nrw.find("dgm1", bbox=(7.555, 51.896, 7.556, 51.897))
    assert len(lonlat) >= 1
    assert sel.area.label.startswith("Punkt 402500,5751500")


def test_tiles_by_geojson(fake, tmp_path):
    gj = {"type": "Feature", "geometry": {"type": "LineString",
                                          "coordinates": [[400500, 5750500], [402500, 5750500]]},
          "crs": {"type": "name", "properties": {"name": "EPSG:25832"}}}
    p = tmp_path / "linie.geojson"
    p.write_text(json.dumps(gj))
    sel = nrw.find("dgm1", geojson=str(p))
    assert keys(sel) == ["400_5750", "401_5750", "402_5750"]


def test_whole_land_without_area(fake):
    assert len(nrw.find("dgm1", with_meta=False)) == 12


def test_admin_product(fake):
    assert [f.key for f in nrw.find("alkis", gemeinde="Telgte")] == ["05570000"]
    assert [f.key for f in nrw.find("alkis", kreis="Münster")] == ["05515000"]
    # geometric selection: a box over the Münster/Warendorf border
    sel = nrw.find("alkis", bbox=(401500, 5750500, 402500, 5751000))
    assert keys(sel) == ["05515000", "05570000"]
    assert sel[0].meta == {"Kreis": "Münster"}
    # a polygon identical to Münster shares only a border with Warendorf
    same = {"type": "Polygon", "coordinates": [[[400000, 5750000], [402000, 5750000],
                                                [402000, 5752000], [400000, 5752000],
                                                [400000, 5750000]]]}
    assert keys(nrw.find("alkis", geojson=same)) == ["05515000"]
    assert len(nrw.find("alkis")) == 4
    lb = nrw.find("landbedeckung", gemeinde="Münster")
    assert [f.name for f in lb] == ["lb_nrw_05500000_Münster_EPSG25832_GeoPackage.zip"]


def test_yearly_admin(fake):
    p = nrw.product("alkis-hist")
    assert p.years() == [2016, 2017]
    sel = nrw.find("alkis-hist", year=2017, kreis="Warendorf")
    assert [f.name for f in sel] == ["2017_gru_vereinf_05570000_Warendorf_EPSG25832_GeoPackage.zip"]
    assert sel[0].subdir == "2017"
    with pytest.raises(ValueError, match="Jahr"):
        nrw.find("alkis-hist", kreis="Warendorf")
    with pytest.raises(ValueError, match="2018"):
        nrw.find("alkis-hist", year=2018, kreis="Warendorf")


def test_single_variants(fake):
    assert [f.name for f in nrw.find("basis-dlm")] == ["basis-dlm_EPSG25832_Shape.zip"]
    assert [f.name for f in nrw.find("basis-dlm", variant="nas")] == ["basis-dlm_EPSG25832_NAS.zip"]
    sel = nrw.find("basis-dlm", gemeinde="Münster")
    assert sel.notes and "landesweit" in sel.notes[0]
    with pytest.raises(ValueError, match="Variante"):
        nrw.find("basis-dlm", variant="gml")


def test_hist_dop_gauss_krueger(fake):
    p = nrw.product("dop-hist")
    assert p.years() == [1952, 2015]
    sel = nrw.find("dop-hist", year=1952, gemeinde="Münster")
    assert sel and {f.crs for f in sel} == {31467}  # Münster lies east of 7.5°E
    assert any("Gauß-Krüger" in n for n in sel.notes)
    assert all(f.date and f.date.startswith("1952-05") for f in sel)
    assert all(f.subdir == "1952" for f in sel)
    sel2015 = nrw.find("dop-hist", year=2015, gemeinde="Münster")
    assert keys(sel2015) == ["400_5750", "400_5751", "401_5750", "401_5751"]
    cov = p.coverage(nrw.area(gemeinde="Telgte"))
    assert cov[1952] > 0 and cov[2015] == 0


def test_wfs_product(fake):
    sel = nrw.find("flurstuecke", gemeinde="Münster")
    assert len(sel) == 1
    f = sel[0]
    assert f.meta["objekte"] == 3 and f.post_data and b"ave:Flurstueck" in f.post_data
    assert f.name == "flurstuecke_gemeinde-muenster-05515000.gpkg"
    with pytest.raises(ValueError, match="Gebiet"):
        nrw.find("flurstuecke")


def test_area_lookup_errors(fake):
    with pytest.raises(LookupError, match="mehrdeutig"):
        grenzen.lookup("gemeinde", "Bad")
    with pytest.raises(LookupError, match="Meinten Sie"):
        grenzen.lookup("gemeinde", "Telgtee")
    assert grenzen.lookup("gemeinde", "Munster").ags == "05515000"
    assert grenzen.lookup("gemeinde", "05515000").name == "Münster"
    assert grenzen.lookup("kreis", "Kreis Warendorf").ags == "05570000"
    assert grenzen.lookup("kreis", "05570").ags == "05570000"
    with pytest.raises(ValueError, match="nur eine"):
        nrw.area(gemeinde="Münster", kreis="Warendorf")


def test_area_helpers():
    a = Area.from_bbox("7.6,51.9,7.7,52.0")
    assert a.shape.crs == 25832 and "EPSG:4326" in a.label
    with pytest.raises(ValueError, match="vertauscht"):
        Area.from_point((51.96, 7.62))
    with pytest.raises(ValueError, match="4 Zahlen"):
        Area.from_bbox("1,2,3")
