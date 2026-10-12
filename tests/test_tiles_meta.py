import pytest

from geobasis.laender.nrw.portal import MetaTable, parse_meta_csv
from geobasis.tiles import parse_tile, parse_year


@pytest.mark.parametrize("name,crs,x,y,size,year", [
    ("dgm1_32_280_5652_1_nw_2022.tif", 25832, 280000, 5652000, 1000, 2022),
    ("ndom50_32280_5652_1_nw_2023.tif", 25832, 280000, 5652000, 1000, 2023),
    ("abk_32280_5657_1.tif", 25832, 280000, 5657000, 1000, None),
    ("LoD2_32_280_5657_1_NW.gml", 25832, 280000, 5657000, 1000, None),
    ("00_dgk5hls_32296_5640_2_nw.tif", 25832, 296000, 5640000, 2000, None),
    ("dtk25_32280_5648_4_nw_col.tif", 25832, 280000, 5648000, 4000, None),
    ("hoeae-s1_32_288_5664_16_EPSG25832_GeoPackage_2020-2024.gpkg", 25832, 288000, 5664000, 16000, None),
    ("3dm_32_280_5652_1_nw.laz", 25832, 280000, 5652000, 1000, None),
    ("dop40pan_2514_5612_2_nw_1951.jp2", 31466, 2514000, 5612000, 2000, 1951),
    ("dop40pan_3396_5688_0_nw_1952.jp2", 31467, 3396000, 5688000, 0, 1952),
])
def test_parse_tile(name, crs, x, y, size, year):
    ref = parse_tile(name)
    assert ref is not None
    assert (ref.crs, ref.x, ref.y, ref.size) == (crs, x, y, size)
    assert parse_year(name) == year


def test_parse_tile_rejects_and_restricts():
    assert parse_tile("gru_vereinf_05711000_Bielefeld_EPSG25832_GeoPackage.zip") is None
    assert parse_tile("dop40pan_2514_5612_2_nw_1951.jp2", 31467) is None
    assert parse_tile("dgm1_32_280_5652_1_nw_2022.tif", 31466) is None
    assert parse_tile("dgm1_32_280_5652_1_nw_2022.tif").key == "280_5652"
    assert parse_tile("dop40pan_3396_5688_0_nw_1952.jp2").bounds(2000) == (3396000, 5688000, 3398000, 5690000)


DGM_CSV = """Kachelinformationen des DGM1 fuer die Datenabgabe
Land;Nordrhein-Westfalen
Aktualitaet_Kachelinformationen;2026-09-30
Kachelname;Aktualitaet;Erfassungsmethode;Fortfuehrung
dgm1_32_280_5652_1_nw_2022;2022-02-28;5020;2022-03-01
dgm1_32_280_5653_1_nw_2022;2022-02-27;5020;
"""

HIST_CSV = """RECHTS;HOCH;BEZEICHNER;JAHRDATEI;EPSG;FLUGDATUM;GSD;KANAELE
2526000.000;5714000.000;4404/07;1952/dop40pan_2526_5714_2_nw_1952.jp2;EPSG:31466;1952-04-11;0.4;PAN
2602000.000;5690000.000;4610/18;1952/dop40pan_2602_5690_0_nw_1952.jp2;EPSG:31466;1952-00-00;0.4;PAN
"""

UTM_HIST_CSV = """RECHTS;HOCH;BEZEICHNER;LOCATION;EPSG;FLUGDATUM;GSD;KANAELE
280000.000;5652000.000;32N2805652;s32280/dop10rgbi_32_280_5652_1_nw_2019.jp2;EPSG:25832;2019-03-30;0.1;RGBI
"""

DGK5_CSV = """Metadaten der DGK5 für die Datenabgabe
Land;Nordrhein-Westfalen
Nummer;Name;SK-Version;Bildflug;Topographie;Spitzenaktualität
dgk5_32278_5654_2_nw;;;;2016-01-12;2016-01-13
"""


def test_meta_kachelname():
    t = parse_meta_csv(DGM_CSV)
    assert isinstance(t, MetaTable) and len(t) == 2
    row = t.lookup("dgm1_32_280_5652_1_nw_2022.tif")
    assert MetaTable.date_of(row) == "2022-02-28"
    assert row["Fortfuehrung"] == "2022-03-01"


def test_meta_hist_gk_and_partial_dates():
    t = parse_meta_csv(HIST_CSV, 31466)
    row = t.lookup("dop40pan_2526_5714_2_nw_1952.jp2")
    assert MetaTable.date_of(row) == "1952-04-11"
    assert MetaTable.date_of(t.lookup("dop40pan_2602_5690_0_nw_1952.jp2")) == "1952"


def test_meta_location_column():
    t = parse_meta_csv(UTM_HIST_CSV, 25832)
    assert MetaTable.date_of(t.lookup("dop10rgbi_32_280_5652_1_nw_2019.jp2")) == "2019-03-30"


def test_meta_falls_back_to_tile_key():
    t = parse_meta_csv(DGK5_CSV)
    row = t.lookup("00_dgk5gru_32278_5654_2_nw.tif", key="278_5654")
    assert MetaTable.date_of(row) == "2016-01-13"
    assert t.lookup("00_dgk5gru_32278_5654_2_nw.tif") is None


def test_meta_without_header():
    assert parse_meta_csv("foo;bar\n1;2\n") is None
