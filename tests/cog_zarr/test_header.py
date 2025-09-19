import textwrap
from pathlib import Path

import pytest

from chris_utils.cog_zarr.header import parse_envi_header


def write_hdr(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "example.hdr"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_parse_basic_numeric_and_strings(tmp_path):
    hdr_path = write_hdr(
        tmp_path,
        """
        ENVI
        description = {Audobon}
        Samples = 766
        lines = 748
        BANDS = 19
        data type = 3
        interleave = bsq
        byte order = 0
        header offset = 0
        temperature = 5.60
        pixel shift coeff = -0.103
        extra shift = -6.7
        sensor type = CHRIS
        """,
    )
    hdr = parse_envi_header(str(hdr_path))

    # keys are lower-cased
    assert "samples" in hdr and "bands" in hdr and "interleave" in hdr

    # ints vs floats
    assert hdr["samples"] == 766
    assert hdr["lines"] == 748
    assert hdr["bands"] == 19
    assert hdr["data type"] == 3
    assert hdr["byte order"] == 0
    assert hdr["header offset"] == 0

    # floats (non-integer)
    assert pytest.approx(hdr["temperature"], rel=0, abs=1e-9) == 5.6
    assert pytest.approx(hdr["pixel shift coeff"], rel=0, abs=1e-9) == -0.103
    assert pytest.approx(hdr["extra shift"], rel=0, abs=1e-9) == -6.7

    # strings preserved
    assert hdr["interleave"] == "bsq"
    assert hdr["sensor type"] == "CHRIS"
    # description had braces but no commas → treated as plain string (after brace strip)
    assert hdr["description"] == "Audobon"


def test_parse_wavelength_list_with_braces(tmp_path):
    hdr_path = write_hdr(
        tmp_path,
        """
        wavelength = {0.0, 442.5, 491.1, 530.8}
        """,
    )
    hdr = parse_envi_header(str(hdr_path))
    assert "wavelength" in hdr
    assert isinstance(hdr["wavelength"], list)
    assert hdr["wavelength"] == pytest.approx([0.0, 442.5, 491.1, 530.8])


def test_parse_wavelength_list_without_braces(tmp_path):
    # The parser treats 'wavelength' specially: commas + key == "wavelength" → list
    hdr_path = write_hdr(
        tmp_path,
        """
        wavelength = 700.0, 710.5, 720.25
        """,
    )
    hdr = parse_envi_header(str(hdr_path))
    assert hdr["wavelength"] == pytest.approx([700.0, 710.5, 720.25])


def test_list_with_non_numeric_items_is_left_as_strings(tmp_path):
    hdr_path = write_hdr(
        tmp_path,
        """
        mylist = {10, foo, 20}
        """,
    )
    hdr = parse_envi_header(str(hdr_path))
    # Conversion to float fails for one element → keep entire list as strings
    assert hdr["mylist"] == ["10", "foo", "20"]


def test_ignores_lines_without_equals_and_trims(tmp_path):
    hdr_path = write_hdr(
        tmp_path,
        """
        # comment-like line without equals
        some noise
        samples=  100
        lines = 200
        """,
    )
    hdr = parse_envi_header(str(hdr_path))
    assert hdr["samples"] == 100
    assert hdr["lines"] == 200
    # no spurious keys created
    assert "#" not in hdr
    assert "some noise" not in hdr


def test_integer_like_floats_become_ints(tmp_path):
    hdr_path = write_hdr(
        tmp_path,
        """
        byte order = 0.0
        header offset = 16.0
        real_float = 5.25
        """,
    )
    hdr = parse_envi_header(str(hdr_path))
    # integer-like floats are coerced to int
    assert hdr["byte order"] == 0
    assert hdr["header offset"] == 16
    # non-integer float stays float
    assert isinstance(hdr["real_float"], float)
    assert pytest.approx(hdr["real_float"], rel=0, abs=1e-9) == 5.25
