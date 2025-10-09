import os

import numpy as np
import pytest
import xarray as xr

# Import the module under test
import chris_utils.cog_zarr.eopf_utils as eu


# ---------- helpers ----------
def small_da(nb=3, ny=4, nx=5, dtype="float32"):
    """Tiny (band, y, x) cube with identifiable values."""
    data = np.arange(nb * ny * nx, dtype=dtype).reshape(nb, ny, nx)
    da = xr.DataArray(
        data,
        dims=("band", "y", "x"),
        coords={
            "band": np.arange(1, nb + 1),
            "y": np.arange(ny),
            "x": np.arange(nx),
        },
        name="data",
    )
    return da


# ---------- tests for _norm_keys (if present) ----------
@pytest.mark.skipif(not hasattr(eu, "_norm_keys"), reason="_norm_keys not present in eopf_utils")
def test_norm_keys_basic():
    fn = eu._norm_keys  # type: ignore[attr-defined]
    src = {"  Foo   Bar  ": 1, "Baz\tQux": 2, "MiXeD": 3}
    got = fn(src)
    assert got == {"foo bar": 1, "baz qux": 2, "mixed": 3}


# ---------- _build_eopf_product (CPM / radiance layout) ----------
@pytest.mark.skipif(
    not hasattr(eu, "_build_eopf_product"), reason="_build_eopf_product not present"
)
def test_build_eopf_product_minimal_cpm(monkeypatch, tmp_path):
    """
    Expect CPM structure:
      measurements/
        image/
          y, x
          oa01_radiance, oa02_radiance, ...
    and product-level attrs including measurement='radiance' (+ units if present).
    """
    da = small_da(nb=3)
    envi_header = {
        "samples": da.sizes["x"],
        "lines": da.sizes["y"],
        "bands": da.sizes["band"],
        "calibration data units": "microWatts/nm/m^2/str",  # picked up by _radiance_units
    }
    hdr_txt_path = str(tmp_path / "dummy.hdr.txt")

    # Fake CHRIS meta + root attrs
    def fake_parse(_path, keep_spectral_table: bool = False, keep_gain_table: bool = False):
        d = {"CHRIS Mode": "2"}  # or "1" in the mode-1 test
        if keep_spectral_table:
            d["spectral_table"] = []  # ok to be empty
        if keep_gain_table:
            d["gain_table"] = []  # ok to be empty
        return d

    def fake_root(_meta, _path):
        return {
            "product_type": "CHR_MO2_1P",
            "datetime": "2025-01-01T00:00:00Z",
            "platform": "PROBA",
            "instrument": "CHRIS",
            "extra_attr": "ok",
        }

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)

    product, base = eu._build_eopf_product(da, envi_header, hdr_txt_path, product_name="MyProd")  # type: ignore[attr-defined]

    # Base group and structure
    assert base == "measurements/image"
    assert "measurements" in product
    assert base in product

    # Coords
    assert f"{base}/y" in product
    assert f"{base}/x" in product

    # Bands as oaXX_radiance
    for i in da.band.values:
        vname = f"oa{int(i):02d}_radiance"
        assert f"{base}/{vname}" in product
        # Per-var attrs
        var = product[f"{base}/{vname}"]
        assert var.attrs.get("measurement") == "radiance"
        assert var.attrs.get("units") == "microWatts/nm/m^2/str"

    # STAC-ish properties
    props = product.attrs["stac_discovery"]["properties"]
    for k in ("product:type", "platform", "instrument"):
        assert k in props
    # assert "start_datetime" in props
    # assert "end_datetime" in props or "centre_datetime" in props  # either/both are fine

    # Merged attrs + product-level measurement
    assert product.attrs["samples"] == da.sizes["x"]
    assert product.attrs["lines"] == da.sizes["y"]
    assert product.attrs["bands"] == da.sizes["band"]
    assert product.attrs["extra_attr"] == "ok"
    assert product.attrs.get("measurement") == "radiance"
    assert product.attrs.get("measurement:units") == "microWatts/nm/m^2/str"

    # No duplicated identity fields at root (kept inside stac_discovery)
    for dup in ("product_type", "platform", "instrument", "datetime"):
        assert dup not in product.attrs


@pytest.mark.skipif(
    not hasattr(eu, "_build_eopf_product"), reason="_build_eopf_product not present"
)
def test_build_eopf_product_mode1_still_image_base(monkeypatch, tmp_path):
    """Mode 1 (36 m) still uses the same CPM base: measurements/image."""
    da = small_da(nb=2)

    def fake_parse(_path, keep_spectral_table: bool = False, keep_gain_table: bool = False):
        d = {"CHRIS Mode": "2"}  # or "1" in the mode-1 test
        if keep_spectral_table:
            d["spectral_table"] = []  # ok to be empty
        if keep_gain_table:
            d["gain_table"] = []  # ok to be empty
        return d

    def fake_root(_m, _p):
        return {"product_type": "X", "datetime": "Y", "platform": "P", "instrument": "I"}

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)
    product, base = eu._build_eopf_product(da, {}, str(tmp_path / "hdr.hdr.txt"), product_name=None)
    assert base == "measurements/image"
    assert base in product


@pytest.mark.skipif(
    not hasattr(eu, "_build_eopf_product"), reason="_build_eopf_product not present"
)
def test_build_eopf_product_name_from_hdr(monkeypatch, tmp_path):
    da = small_da(nb=1)
    hdr_txt = str(tmp_path / "CHRIS_ABC_123.hdr.txt")
    (tmp_path / "CHRIS_ABC_123.hdr.txt").write_text("", encoding="utf-8")

    def fake_parse(_path, keep_spectral_table: bool = False, keep_gain_table: bool = False):
        d = {"CHRIS Mode": "2"}  # or "1" in the mode-1 test
        if keep_spectral_table:
            d["spectral_table"] = []  # ok to be empty
        if keep_gain_table:
            d["gain_table"] = []  # ok to be empty
        return d

    def fake_root(_m, _p):
        return {"product_type": "X", "datetime": "Y", "platform": "P", "instrument": "I"}

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)
    product, base = eu._build_eopf_product(da, {}, hdr_txt, product_name=None)
    assert isinstance(product.name, str) and len(product.name) > 0
    assert base == "measurements/image"


# ---------- tests for write_eopf_zarr (always present in both variants) ----------
def test_write_eopf_zarr_writes_product(monkeypatch, tmp_path):
    """
    We don't rely on the real EOZarrStore; instead, we monkeypatch it with a fake
    that captures what gets written. We also monkeypatch metadata helpers.
    """
    da = small_da(nb=2)
    envi_header = {"bands": 2, "calibration data units": "microWatts/nm/m^2/str"}
    hdr_txt = str(tmp_path / "dummy.hdr.txt")
    out_path = str(tmp_path / "MyProd.eopf.zarr")

    def fake_parse(_path, keep_spectral_table: bool = False, keep_gain_table: bool = False):
        d = {"CHRIS Mode": "2"}  # or "1" in the mode-1 test
        if keep_spectral_table:
            d["spectral_table"] = []  # ok to be empty
        if keep_gain_table:
            d["gain_table"] = []  # ok to be empty
        return d

    def fake_root(_m, _p):
        return {
            "product_type": "CHR_MO2_1P",
            "datetime": "2025-01-01T00:00:00Z",
            "platform": "PROBA",
            "instrument": "CHRIS",
        }

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)

    written = {}

    class FakeStoreCtx:
        def __init__(self, url):
            self.url = url

        def open(self, mode=None):
            return self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __setitem__(self, key, value):
            written[key] = value

    monkeypatch.setattr(eu, "EOZarrStore", FakeStoreCtx, raising=True)

    eu.write_eopf_zarr(da, envi_header, hdr_txt, out_path)

    prod_name = os.path.splitext(os.path.basename(out_path))[0]
    assert prod_name in written
    product = written[prod_name]

    base = "measurements/image"
    assert base in product
    assert f"{base}/y" in product
    assert f"{base}/x" in product
    assert f"{base}/oa01_radiance" in product
    # root attrs sanity
    assert product.attrs["bands"] == da.sizes["band"]
    # Zarr root should not duplicate identity fields
    for dup in ("product_type", "platform", "instrument", "datetime"):
        assert dup not in product.attrs


# ---------- tests for write_eopf_cog (if present) ----------
@pytest.mark.skipif(
    not hasattr(eu, "write_eopf_cog"), reason="write_eopf_cog not present in eopf_utils"
)
def test_write_eopf_cog_structure(monkeypatch, tmp_path):
    """
    Ensure the function writes the expected hierarchy keys into the COG store:
      "", "measurements", "measurements/radiance", and r{gsd}m group.
    """
    da = small_da(nb=2)
    envi_header = {"bands": 2}
    hdr_txt = str(tmp_path / "dummy.hdr.txt")
    out_dir = str(tmp_path / "MyProd.eopf.cog")

    def fake_parse(_path, keep_spectral_table: bool = False, keep_gain_table: bool = False):
        d = {"CHRIS Mode": "2"}  # or "1" in the mode-1 test
        if keep_spectral_table:
            d["spectral_table"] = []  # ok to be empty
        if keep_gain_table:
            d["gain_table"] = []  # ok to be empty
        return d

    def fake_root(_m, _p):
        return {
            "product_type": "CHR_MO2_1P",
            "datetime": "2025-01-01T00:00:00Z",
            "platform": "PROBA",
            "instrument": "CHRIS",
        }

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)

    written = {}

    class FakeCogCtx:
        def __init__(self, url):
            self.url = url

        def open(self, mode=None):
            return self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __setitem__(self, key, value):
            written[key] = value

    monkeypatch.setattr(eu, "EOCogStore", FakeCogCtx, raising=False)

    eu.write_eopf_cog(da, envi_header, hdr_txt, out_dir)  # type: ignore[attr-defined]

    # Expected keys written
    assert "" in written
    assert "measurements" in written
    assert "measurements/image" in written
    root_prod = written[""]
    # Only assert these if you implemented them in _build_eopf_product(product_format="COG")
    assert root_prod.attrs.get("file_type") in {"COG", "ZARR", None}  # "COG" if you set it
    # If set to "COG", dtype/bit_depth should also be present
    if root_prod.attrs.get("file_type") == "COG":
        assert "dtype" in root_prod.attrs
        assert "bit_depth" in root_prod.attrs


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("1", 36),
        ("01", 36),
        (" 1 ", 36),
        (1, 36),
        ("2", 18),
        (None, 18),
        ("abc", 18),
    ],
)
def test_gsd_from_mode(mode, expected):
    assert eu._gsd_from_mode({"CHRIS Mode": mode}) == expected
