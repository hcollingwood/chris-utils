import os
from pathlib import Path

import pytest

from chris_utils.cog_zarr.hdr_parser import build_eopf_root_attrs, parse_chris_hdr_txt


# -----------------------------
# Utilities
# -----------------------------
def write(txt_path: Path, text: str) -> None:
    txt_path.write_text(text, encoding="utf-8")


# -----------------------------
# parse_chris_hdr_txt tests
# -----------------------------
def test_parse_hdr_inline_and_nextline_and_table(tmp_path: Path):
    """
    - Parses inline (tab & multi-space) key/vals
    - Parses 'key on comment line, value on next non-comment line'
    - Collects spectral table rows when keep_spectral_table=True
    """
    p = tmp_path / "CHRIS_sample.hdr.txt"
    content = "\n".join(
        [
            "//CHRIS Mode\t2",  # inline (tab)
            "//Sensor Type  CHRIS",  # inline (multi-space)
            "//Image Date (yyyy-mm-dd)",  # key on comment line...
            "2004-04-11",  # ...value on next non-comment line
            "//Calculated Image Centre Time\t12:34:56",  # inline (tab)
            "//Some Section Attributes",  # should be ignored
            "//WLLOW  WLCENTR  WLUPPER",  # table header (comment)
            "//400.0  405.0    410.0",  # first row (comment)
            "420.0  425.0    430.0",  # second row (non-comment)
        ]
    )
    write(p, content)

    meta = parse_chris_hdr_txt(str(p), keep_spectral_table=True)

    # Basic keys
    assert meta["CHRIS Mode"] == "2"
    assert meta["Sensor Type"] == "CHRIS"
    assert meta["Image Date (yyyy-mm-dd)"] == "2004-04-11"
    assert meta["Calculated Image Centre Time"] == "12:34:56"

    # Spectral table collected
    assert "spectral_table" in meta
    rows = meta["spectral_table"]
    assert isinstance(rows, list)
    assert len(rows) == 2
    # Each row is a dict with WLLOW/WLCENTR/WLUPPER
    assert set(rows[0].keys()) == {"WLLOW", "WLCENTR", "WLUPPER"}
    assert rows[0]["WLLOW"] == "400.0"
    assert rows[1]["WLCENTR"] == "425.0"


def test_parse_hdr_no_table_when_flag_false(tmp_path: Path):
    p = tmp_path / "meta.hdr.txt"
    write(
        p,
        "//WLLOW  WLCENTR  WLUPPER\n//400  405  410\n",
    )
    meta = parse_chris_hdr_txt(str(p), keep_spectral_table=False)
    assert "spectral_table" not in meta  # ignored


def test_parse_hdr_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_chris_hdr_txt("does/not/exist.hdr.txt")


def test_parse_hdr_unreadable_raises(monkeypatch, tmp_path: Path):
    """
    Simulate unreadable file via os.access returning False.
    (More reliable across platforms than chmod(000) in CI.)
    """
    p = tmp_path / "meta.hdr.txt"
    write(p, "//Key\tValue\n")

    def fake_isfile(path):
        return True

    def fake_access(path, mode):
        # Deny read access only for our path
        return False

    monkeypatch.setattr(os.path, "isfile", fake_isfile)
    monkeypatch.setattr(os, "access", fake_access)

    with pytest.raises(PermissionError):
        parse_chris_hdr_txt(str(p))


# -----------------------------
# build_eopf_root_attrs tests
# -----------------------------
def test_build_eopf_root_attrs_happy_path(tmp_path: Path):
    chris_meta = {
        "Image Date (yyyy-mm-dd)": "2004-10-13",
        "Calculated Image Centre Time": "12:34:56",
        "Sensor Type": "CHRIS",
        # Note spelling “Lattitude” mirrors your parser’s expectation
        "Longitude": "-1.2345",
        "Lattitude": "52.3456",
        "Some Other Field (km/s)": "foo bar",
    }
    hdr_fn = tmp_path / "CHRIS_GP_041013_47F4_41.hdr.txt"

    out = build_eopf_root_attrs(chris_meta, str(hdr_fn))

    # ID derived by stripping .hdr/.txt
    assert out["id"] == "CHRIS_GP_041013_47F4_41"
    assert out["product_type"] == "CHRIS-RCI"
    # ISO datetime from date + centre time
    assert out["datetime"] == "2004-10-13T12:34:56Z"
    # Platform & instrument
    assert out["platform"] == "ESA PROBA"
    assert out["instrument"] == "CHRIS"
    # Center coordinates
    assert out["center_lon"] == "-1.2345"
    assert out["center_lat"] == "52.3456"
    # Prefixed & sanitized extra fields
    # "Some Other Field (km/s)" -> "chris_some_other_field_km_s_"
    assert out["chris_some_other_field_km_s_"] == "foo bar"
    # Also the original common fields are copied under chris_* unless they collide
    assert out["chris_image_date_yyyy_mm_dd_"] == "2004-10-13"
    assert out["chris_calculated_image_centre_time"] == "12:34:56"
    assert out["chris_sensor_type"] == "CHRIS"


def test_build_eopf_root_attrs_bad_time_falls_back(tmp_path: Path):
    chris_meta = {
        "Image Date (yyyy-mm-dd)": "2004-10-13",
        # malformed centre time
        "Calculated Image Centre Time": "12-34-56",
    }
    hdr_fn = tmp_path / "whatever.hdr"

    out = build_eopf_root_attrs(chris_meta, str(hdr_fn))
    # Falls back to concatenation with 'Z'
    assert out["datetime"] == "2004-10-13T12-34-56Z"
    # id strips only .hdr
    assert out["id"] == "whatever"


def test_parse_hdr_skips_malformed_rows(tmp_path):
    p = tmp_path / "meta.hdr.txt"
    p.write_text(
        "//WLLOW  WLCENTR  WLUPPER\n"
        "//400  405  410\n"
        "//500  505\n",  # malformed (2 cols instead of 3) -> should be skipped
        encoding="utf-8",
    )
    meta = parse_chris_hdr_txt(str(p), keep_spectral_table=True)
    rows = meta["spectral_table"]
    assert len(rows) == 1
    assert rows[0]["WLLOW"] == "400"


def test_build_eopf_root_attrs_missing_fields(tmp_path):
    chris_meta = {
        "Image Date (yyyy-mm-dd)": "2004-10-13",
        "Calculated Image Centre Time": "12:34:56",
        # no Sensor Type, no Lon/Lat
    }
    hdr_fn = tmp_path / "name.hdr.txt"
    out = build_eopf_root_attrs(chris_meta, str(hdr_fn))
    assert out["platform"] == "ESA PROBA"
    assert "instrument" not in out
    assert "center_lon" not in out and "center_lat" not in out
