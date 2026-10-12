import json

from geobasis.cli import main


def test_produkte(capsys):
    assert main(["produkte"]) == 0
    out = capsys.readouterr().out
    assert "dgm1" in out and "Höhenmodelle" in out and "dl-de/zero-2-0" in out


def test_produkte_json(capsys):
    assert main(["produkte", "--json", "--kategorie", "luftbild"]) == 0
    ids = [p["id"] for p in json.loads(capsys.readouterr().out)]
    assert "dop10" in ids and "dgm1" not in ids


def test_info(fake, capsys):
    assert main(["info", "dgm1"]) == 0
    out = capsys.readouterr().out
    assert "12 (" in out  # newest version per tile


def test_suche_and_footprints(fake, capsys, tmp_path):
    gj = tmp_path / "u.geojson"
    assert main(["suche", "dgm1", "--gemeinde", "Münster", "--umrisse", str(gj)]) == 0
    out = capsys.readouterr().out
    assert "Gemeinde Münster" in out and "dgm1_32_400_5750_1_nw_2024.tif" in out
    assert json.loads(gj.read_text())["features"]
    assert main(["suche", "dgm1", "--kreis", "Münster", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["product"] == "dgm1"


def test_download_dry_run(fake, capsys, tmp_path):
    assert main(["download", "dgm1", "--punkt", "400500,5750500", "-o", str(tmp_path), "--probelauf"]) == 0
    assert "http://127.0.0.1" in capsys.readouterr().out
    assert not (tmp_path / "dgm1").exists()


def test_download(fake, capsys, tmp_path):
    assert main(["download", "dgm1", "--punkt", "400500,5750500", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "dgm1" / "dgm1_32_400_5750_1_nw_2024.tif").exists()


def test_jahre(fake, capsys):
    assert main(["jahre", "dop-hist"]) == 0
    assert capsys.readouterr().out.split() == ["1952", "2015"]
    assert main(["jahre", "dop-hist", "--gemeinde", "Münster"]) == 0
    assert "2015" in capsys.readouterr().out


def test_gemeinden_and_dienste(fake, capsys):
    assert main(["gemeinden", "bad"]) == 0
    out = capsys.readouterr().out
    assert "Bad Honnef" in out and "Telgte" not in out
    assert main(["gemeinden", "--kreise"]) == 0
    assert "Warendorf" in capsys.readouterr().out
    assert main(["dienste"]) == 0
    assert "wms_nw_dop" in capsys.readouterr().out


def test_portal(fake, capsys, tmp_path):
    assert main(["portal", "geobasis/lm/akt/basis-dlm"]) == 0
    assert "basis-dlm_EPSG25832_NAS.zip" in capsys.readouterr().out
    assert main(["portal", "geobasis/lm/akt/basis-dlm", "--laden", "*NAS*", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "basis-dlm_EPSG25832_NAS.zip").exists()


def test_errors(fake, capsys):
    assert main(["suche", "dgm2"]) == 2
    assert "Meinten Sie" in capsys.readouterr().err
    assert main(["suche", "dgm1", "--gemeinde", "Atlantis"]) == 2
    assert main(["--land", "by", "produkte"]) == 2
    assert "nicht unterstützt" in capsys.readouterr().err


def test_cache(capsys):
    assert main(["cache"]) == 0
    assert main(["cache", "--leeren"]) == 0
