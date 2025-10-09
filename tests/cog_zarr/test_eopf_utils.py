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
    def fake_parse(_):
        return {"CHRIS Mode": "2"}  # -> 18 m (not encoded in path now)

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
    for k in ("product:type", "start_datetime", "platform", "instrument"):
        assert k in props

    # Merged attrs + product-level measurement
    assert product.attrs["samples"] == da.sizes["x"]
    assert product.attrs["lines"] == da.sizes["y"]
    assert product.attrs["extra_attr"] == "ok"
    assert product.attrs.get("measurement") == "radiance"
    assert product.attrs.get("measurement:units") == "microWatts/nm/m^2/str"


@pytest.mark.skipif(
    not hasattr(eu, "_build_eopf_product"), reason="_build_eopf_product not present"
)
def test_build_eopf_product_mode1_still_image_base(monkeypatch, tmp_path):
    """Mode 1 (36 m) still uses the same CPM base: measurements/image."""
    da = small_da(nb=2)

    def fake_parse(_):
        return {"CHRIS Mode": "1"}  # -> 36 m

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

    def fake_parse(_):
        return {"CHRIS Mode": "2"}

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

    def fake_parse(_):
        return {"CHRIS Mode": "2"}

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

    def fake_parse(_):
        return {"CHRIS Mode": "2"}

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


def _small_da(nb=2, ny=3, nx=4):
    data = np.arange(nb * ny * nx, dtype="float32").reshape(nb, ny, nx)
    return xr.DataArray(
        data,
        dims=("band", "y", "x"),
        coords={"band": np.arange(1, nb + 1), "y": np.arange(ny), "x": np.arange(nx)},
    )


@pytest.mark.skipif(
    not hasattr(eu, "_build_eopf_product"), reason="_build_eopf_product not present"
)
def test_eopf_uses_geo_helpers_for_crs_and_geometry(monkeypatch, tmp_path):
    da = _small_da()
    # Inject spatial_ref onto da so geo_epsg_from_da returns a code
    da.attrs["spatial_ref"] = "EPSG:32612"

    # Monkeypatch parse/root to avoid real hdr.txt
    monkeypatch.setattr(eu, "parse_chris_hdr_txt", lambda p: {"CHRIS Mode": "2"}, raising=True)
    monkeypatch.setattr(
        eu,
        "build_eopf_root_attrs",
        lambda m, p: {"product_type": "X", "datetime": "Y", "platform": "P", "instrument": "I"},
        raising=True,
    )

    # Monkeypatch geo helpers:
    monkeypatch.setattr(eu, "geo_epsg_from_da", lambda _da: 32612, raising=True)

    def fake_geom_arrays(_da, _meta):
        return {
            "sza": np.full((da.sizes["y"], da.sizes["x"]), 45.0, dtype="float32"),
            "oza": np.full((da.sizes["y"], da.sizes["x"]), 10.0, dtype="float32"),
        }

    monkeypatch.setattr(eu, "geo_constant_geometry_arrays", fake_geom_arrays, raising=True)

    product, base = eu._build_eopf_product(
        da,
        {"calibration data units": "uW/nm/m^2/sr"},
        str(tmp_path / "dummy.hdr.txt"),
        product_name="Prod",
    )

    # CRS variable exists and has grid mapping attrs
    assert f"{base}/crs" in product
    crs_var = product[f"{base}/crs"]
    assert crs_var.attrs.get("spatial_ref") == "EPSG:32612"

    # geometry group exists with sza/oza and has grid_mapping attr
    assert "conditions" in product and "geometry" in product["conditions"]
    for k in ("sza", "oza"):
        v = product[f"conditions/geometry/{k}"]
        assert v.dims == ("y", "x")
        assert v.attrs.get("grid_mapping") == "crs"

    # measurements are present and tagged
    for i in da.band.values:
        vname = f"oa{int(i):02d}_radiance"
        v = product[f"{base}/{vname}"]
        assert v.attrs.get("measurement") == "radiance"
        assert v.attrs.get("units") == "uW/nm/m^2/sr"


def test_build_eopf_product_with_crs_and_geometry(monkeypatch, tmp_path):
    import chris_utils.cog_zarr.eopf_utils as eu

    da = small_da(nb=1)
    da.attrs["spatial_ref"] = "EPSG:32612"

    monkeypatch.setattr(eu, "parse_chris_hdr_txt", lambda p: {}, raising=True)
    monkeypatch.setattr(
        eu,
        "build_eopf_root_attrs",
        lambda m, p: {"product_type": "X", "datetime": "Y", "platform": "P", "instrument": "I"},
        raising=True,
    )
    monkeypatch.setattr(eu, "geo_epsg_from_da", lambda _da: 32612, raising=True)
    monkeypatch.setattr(
        eu,
        "geo_constant_geometry_arrays",
        lambda _da, _m: {"sza": np.zeros((da.sizes["y"], da.sizes["x"]), dtype="float32")},
        raising=True,
    )

    product, base = eu._build_eopf_product(
        da, {}, str(tmp_path / "dummy.hdr.txt"), product_name="P"
    )
    assert f"{base}/crs" in product
    assert "conditions/geometry/sza" in product
