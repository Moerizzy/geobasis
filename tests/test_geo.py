import math

import pytest

from geobasis.geo import (
    GK2,
    UTM32,
    BBox,
    Shape,
    ShapeIndex,
    guess_crs,
    parse_crs,
    segment_intersects_rect,
    transformer,
)

# reference values computed with pyproj/PROJ 9
UTM_REF = [
    ((7.6261, 51.9625), (405604.3943122278, 5757758.827204256)),
    ((6.958, 50.941), (356538.2618164583, 5645249.362899656)),
    ((9.0, 52.0), (500000.0, 5761038.212466577)),
    ((6.0, 51.0), (289511.14296254923, 5654109.178603593)),
]


@pytest.mark.parametrize("ll,en", UTM_REF)
def test_utm_forward_matches_proj(ll, en):
    e, n = UTM32.forward(*ll)
    assert e == pytest.approx(en[0], abs=1e-3)
    assert n == pytest.approx(en[1], abs=1e-3)


@pytest.mark.parametrize("ll,en", UTM_REF)
def test_utm_inverse_roundtrip(ll, en):
    lon, lat = UTM32.inverse(*en)
    assert lon == pytest.approx(ll[0], abs=1e-9)
    assert lat == pytest.approx(ll[1], abs=1e-9)


@pytest.mark.parametrize("code,ll,ref", [
    (31466, (7.6261, 51.9625), (2611808.117, 5759982.098)),
    (31467, (7.6261, 51.9625), (3405639.239, 5759622.253)),
    (31466, (6.958, 50.941), (2567376.090, 5645520.512)),
])
def test_gauss_krueger_within_a_few_metres(code, ll, ref):
    x, y = transformer(4326, code)(*ll)
    assert math.hypot(x - ref[0], y - ref[1]) < 3.0
    lon, lat = transformer(code, 4326)(x, y)
    assert (lon, lat) == pytest.approx(ll, abs=1e-7)


def test_web_mercator():
    x, y = transformer(4326, 3857)(7.6261, 51.9625)
    assert (x, y) == pytest.approx((848933.5687, 6793347.8115), abs=1e-3)


def test_gk_central_meridian_has_no_easting_offset():
    x, _ = GK2.forward(6.0, 51.0)
    assert x == pytest.approx(2500000.0, abs=1e-6)


def test_parse_and_guess_crs():
    assert parse_crs("EPSG:25832") == 25832
    assert parse_crs("urn:ogc:def:crs:EPSG::4326") == 4326
    assert parse_crs("urn:ogc:def:crs:OGC:1.3:CRS84") == 4326
    assert parse_crs(None) is None
    assert guess_crs(7.6, 51.9) == 4326
    assert guess_crs(405000, 5757000) == 25832
    assert guess_crs(32405000, 5757000) == 4647
    assert guess_crs(2611808, 5759982) == 31466
    with pytest.raises(ValueError):
        guess_crs(1e9, 1e9)


def test_segment_rect():
    r = (0, 0, 10, 10)
    assert segment_intersects_rect(-5, 5, 15, 5, *r)  # crosses
    assert segment_intersects_rect(2, 2, 3, 3, *r)  # inside
    assert not segment_intersects_rect(-5, -5, -1, 20, *r)  # left of it
    assert segment_intersects_rect(5, 5, 5, 5, *r)  # point inside
    assert not segment_intersects_rect(11, 5, 11, 5, *r)  # point outside
    assert segment_intersects_rect(-1, 11, 11, -1, *r)  # diagonal through


def test_strict_segment_rect():
    r = (0, 0, 10, 10)
    assert not segment_intersects_rect(0, -5, 0, 15, *r, strict=True)  # along the border
    assert not segment_intersects_rect(-5, 5, 5, 15, *r, strict=True)  # touches a corner
    assert segment_intersects_rect(-5, 5, 5, 6, *r, strict=True)


def test_touching_tiles_do_not_count():
    sq = ShapeIndex(Shape.from_bbox(0, 0, 10, 10))
    assert not sq.intersects_rect(10, 0, 20, 10)  # shares an edge
    assert not sq.intersects_rect(10, 10, 20, 20)  # shares a corner
    assert sq.intersects_rect(9, 0, 20, 10)
    line = ShapeIndex(Shape(lines=[[(10, 0), (10, 10)]]))
    assert line.intersects_rect(10, 0, 20, 10)  # lines count when touching


def test_shape_index_triangle():
    tri = Shape(rings=[[(0, 0), (10, 0), (0, 10)]])
    idx = ShapeIndex(tri, cell=1)
    assert idx.intersects_rect(1, 1, 2, 2)  # inside
    assert idx.intersects_rect(4, 4, 6, 6)  # crosses hypotenuse
    assert not idx.intersects_rect(7, 7, 9, 9)  # beyond hypotenuse
    assert idx.intersects_rect(-5, -5, 20, 20)  # contains whole triangle
    assert not idx.intersects_rect(20, 20, 30, 30)


def test_shape_index_hole():
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    hole = [(40, 40), (60, 40), (60, 60), (40, 60)]
    idx = ShapeIndex(Shape(rings=[outer, hole]))
    assert not idx.intersects_rect(45, 45, 55, 55)  # inside the hole
    assert idx.intersects_rect(35, 45, 45, 55)  # touches hole edge
    assert idx.intersects_rect(10, 10, 20, 20)
    assert idx.contains_point(10, 10)
    assert not idx.contains_point(50, 50)


def test_shape_index_lines_and_points():
    line = Shape(lines=[[(0, 0), (100, 100)]])
    idx = ShapeIndex(line)
    assert idx.intersects_rect(45, 45, 55, 55)
    assert not idx.intersects_rect(60, 0, 70, 10)
    pt = Shape(lines=[[(5, 5), (5, 5)]])
    assert ShapeIndex(pt).intersects_rect(0, 0, 10, 10)
    assert not ShapeIndex(pt).intersects_rect(6, 6, 10, 10)


def test_circle_covers_radius():
    c = Shape.circle(0, 0, 100)
    idx = ShapeIndex(c)
    assert idx.contains_point(99.9, 0)
    assert idx.contains_point(0, -99.9)
    assert not idx.contains_point(80, 80)  # outside the circle


def test_intersects_shape():
    a = Shape(rings=[[(0, 0), (10, 0), (10, 10), (0, 10)]])
    idx = ShapeIndex(a)
    assert idx.intersects_shape(Shape(rings=[[(5, 5), (15, 5), (15, 15), (5, 15)]]))  # overlap
    assert idx.intersects_shape(Shape(rings=[[(2, 2), (3, 2), (3, 3)]]))  # contained
    assert idx.intersects_shape(Shape(rings=[[(-5, -5), (20, -5), (20, 20), (-5, 20)]]))  # contains
    assert not idx.intersects_shape(Shape(rings=[[(20, 20), (30, 20), (30, 30)]]))
    assert idx.intersects_shape(Shape(lines=[[(-5, 5), (15, 5)]]))  # line crossing
    assert not idx.intersects_shape(Shape.from_bbox(10, 0, 20, 10))  # shared border only
    assert idx.intersects_shape(Shape.from_bbox(0, 0, 10, 10))  # identical
    assert idx.intersects_shape(Shape.from_bbox(0, 0, 5, 10))  # inside, sharing borders
    ring_with_hole = Shape(rings=[[(-50, -50), (50, -50), (50, 50), (-50, 50)],
                                  [(-20, -20), (30, -20), (30, 30), (-20, 30)]])
    assert not ShapeIndex(ring_with_hole).intersects_shape(a)  # a lies in the hole
    assert not idx.intersects_shape(ring_with_hole)


def test_from_geojson_and_transform():
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": {
            "type": "Polygon", "coordinates": [[[7.62, 51.96], [7.63, 51.96], [7.63, 51.97],
                                                [7.62, 51.97], [7.62, 51.96]]]}},
        {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [7.0, 51.0]}},
    ]}
    s = Shape.from_geojson(fc)
    assert s.crs == 4326 and len(s.rings) == 1 and len(s.lines) == 1
    u = s.transform(25832)
    assert u.crs == 25832
    assert 404000 < u.rings[0][0][0] < 406000
    # the projected square is ~690 m x 1110 m
    assert 0.7e6 < Shape(rings=u.rings).area < 0.8e6
    named = {"type": "FeatureCollection",
             "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25832"}},
             "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [400000, 5750000]}}]}
    assert Shape.from_geojson(named).crs == 25832


def test_bbox_validation():
    with pytest.raises(ValueError):
        BBox(10, 0, 0, 10)
    assert BBox(0, 0, 10, 10).intersects(BBox(10, 10, 20, 20))
    with pytest.raises(ValueError):
        Shape(rings=[])
