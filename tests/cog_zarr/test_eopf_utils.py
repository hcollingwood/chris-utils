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


# ---------- tests for _build_eopf_product (if present) ----------
@pytest.mark.skipif(
    not hasattr(eu, "_build_eopf_product"), reason="_build_eopf_product not present in eopf_utils"
)
def test_build_eopf_product_minimal(monkeypatch, tmp_path):
    """
    Verifies:
      - EOProduct returned with correct group path (r18m for CHRIS mode 2)
      - y/x coords present
      - bXX variables present
      - stac_discovery props present
      - attrs merged from ENVI + root attrs
    """
    da = small_da(nb=3)
    envi_header = {"samples": da.sizes["x"], "lines": da.sizes["y"], "bands": da.sizes["band"]}
    hdr_txt_path = str(tmp_path / "dummy.hdr.txt")

    # Fake CHRIS meta + root attrs
    def fake_parse(_):
        return {"CHRIS Mode": "2"}  # => r18m

    def fake_root(_meta, _path):
        return {
            "product_type": "CHR_MO2_1P",
            "datetime": "2025-01-01T00:00:00Z",
            "platform": "PROBA",
            "instrument": "CHRIS",
            "extra_attr": "ok",
        }

    # Patch the helpers used by _build_eopf_product
    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)

    product, res_grp = eu._build_eopf_product(da, envi_header, hdr_txt_path, product_name="MyProd")  # type: ignore[attr-defined]

    # Group path and basic structure
    assert res_grp == "measurements/reflectance/r18m"
    assert "measurements" in product
    assert "measurements/reflectance" in product
    assert res_grp in product

    # coords
    assert f"{res_grp}/y" in product
    assert f"{res_grp}/x" in product

    # bands
    for i in da.band.values:
        bname = f"b{int(i):02d}"
        assert f"{res_grp}/{bname}" in product

    # stac_discovery
    props = product.attrs["stac_discovery"]["properties"]
    for k in ("product:type", "start_datetime", "platform", "instrument"):
        assert k in props

    # merged attrs
    assert product.attrs["samples"] == da.sizes["x"]
    assert product.attrs["lines"] == da.sizes["y"]
    assert product.attrs["extra_attr"] == "ok"


# ---------- tests for write_eopf_zarr (always present in both variants) ----------
def test_write_eopf_zarr_writes_product(monkeypatch, tmp_path):
    """
    We don't rely on the real EOZarrStore; instead, we monkeypatch it with a fake
    that captures what gets written. We also monkeypatch metadata helpers.
    """
    da = small_da(nb=2)
    envi_header = {"bands": 2}
    hdr_txt = str(tmp_path / "dummy.hdr.txt")
    out_path = str(tmp_path / "MyProd.eopf.zarr")

    # Fake CHRIS meta + root attrs
    def fake_parse(_):
        return {"CHRIS Mode": "2"}  # => r18m

    def fake_root(_meta, _path):
        return {
            "product_type": "CHR_MO2_1P",
            "datetime": "2025-01-01T00:00:00Z",
            "platform": "PROBA",
            "instrument": "CHRIS",
        }

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    # Some versions import the helpers as build_eopf_root_attrs; others as eopf_root
    if hasattr(eu, "build_eopf_root_attrs"):
        monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)

    # Fake EOZarrStore that records writes
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
            written[key] = value  # key = product.name, value = EOProduct

    # Monkeypatch class EOZarrStore to our fake
    monkeypatch.setattr(eu, "EOZarrStore", FakeStoreCtx, raising=True)

    # Call function under test
    eu.write_eopf_zarr(da, envi_header, hdr_txt, out_path)

    # Verify directory created and write happened
    assert os.path.isdir(tmp_path)
    # The key written should be the product name = basename without ".zarr"
    prod_name = os.path.splitext(os.path.basename(out_path))[0]
    assert prod_name in written

    product = written[prod_name]
    # Basic expectations about produced content
    grp = "measurements/reflectance/r18m"
    assert grp in product
    assert f"{grp}/y" in product
    assert f"{grp}/x" in product
    assert f"{grp}/b01" in product  # first band exists


# ---------- tests for write_eopf_cog (if present) ----------
@pytest.mark.skipif(
    not hasattr(eu, "write_eopf_cog"), reason="write_eopf_cog not present in eopf_utils"
)
def test_write_eopf_cog_structure(monkeypatch, tmp_path):
    """
    Ensure the function writes the expected hierarchy keys into the COG store:
      "", "measurements", "measurements/reflectance", and r{gsd}m group.
    """
    da = small_da(nb=2)
    envi_header = {"bands": 2}
    hdr_txt = str(tmp_path / "dummy.hdr.txt")
    out_dir = str(tmp_path / "MyProd.eopf.cog")

    def fake_parse(_):
        return {"CHRIS Mode": "2"}

    def fake_root(_meta, _path):
        return {
            "product_type": "CHR_MO2_1P",
            "datetime": "2025-01-01T00:00:00Z",
            "platform": "PROBA",
            "instrument": "CHRIS",
        }

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)

    # Fake EOCogStore
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

    # We expect these keys at least
    assert "" in written
    assert "measurements" in written
    assert "measurements/reflectance" in written
    assert "measurements/reflectance/r18m" in written


@pytest.mark.skipif(
    not hasattr(eu, "_build_eopf_product"), reason="_build_eopf_product not present"
)
def test_build_eopf_product_mode1_r36m(monkeypatch, tmp_path):
    da = small_da(nb=2)

    def fake_parse(_):
        return {"CHRIS Mode": "1"}  # -> r36m

    def fake_root(_m, _p):
        return {"product_type": "X", "datetime": "Y", "platform": "P", "instrument": "I"}

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)
    product, grp = eu._build_eopf_product(da, {}, str(tmp_path / "hdr.hdr.txt"), product_name=None)
    assert grp == "measurements/reflectance/r36m"


@pytest.mark.skipif(
    not hasattr(eu, "_build_eopf_product"), reason="_build_eopf_product not present"
)
def test_build_eopf_product_name_from_hdr(monkeypatch, tmp_path):
    da = small_da(nb=1)
    hdr_txt = str(tmp_path / "CHRIS_ABC_123.hdr.txt")
    (tmp_path / "CHRIS_ABC_123.hdr.txt").write_text("", encoding="utf-8")

    def fake_parse(_):
        return {"CHRIS Mode": "2"}

    def fake_root(_m, _p):
        return {"product_type": "X", "datetime": "Y", "platform": "P", "instrument": "I"}

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", fake_parse, raising=False)
    monkeypatch.setattr(eu, "build_eopf_root_attrs", fake_root, raising=False)
    product, grp = eu._build_eopf_product(da, {}, hdr_txt, product_name=None)
    # When product_name is None, _build_eopf_product derives the name from hdr_txt
    assert isinstance(product.name, str) and len(product.name) > 0
