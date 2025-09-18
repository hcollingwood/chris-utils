import numpy as np
import pytest

from chris_utils.cog_zarr.reader import RCIReader

# ------------------------
# helpers to build tiny test files
# ------------------------


def write_envi_header(
    path, *, samples, lines, bands, dtype_code=3, interleave="bsq", wavelengths=None, byte_order=0
):
    """
    Minimal ENVI header writer matching the parser expectations.
    dtype_code: ENVI data type code (3 = int32)
    """
    wavelengths = wavelengths or []
    wls_str = "{" + ",".join(str(float(v)) for v in wavelengths) + "}" if wavelengths else "{}"
    txt = (
        "ENVI\n"
        "description = {unit test}\n"
        f"samples = {samples}\n"
        f"lines = {lines}\n"
        f"bands = {bands}\n"
        "header offset = 0\n"
        "file type = ENVI Standard\n"
        f"data type = {dtype_code}\n"
        f"interleave = {interleave}\n"
        "sensor type = CHRIS\n"
        f"byte order = {byte_order}\n"
        f"wavelength = {wls_str}\n"
    )
    with open(path, "w") as f:
        f.write(txt)


def write_rci(path, arr, interleave="bsq"):
    """
    Write raw binary in the layout the header declares.
    arr should be shaped as:
      - BSQ: (bands, lines, samples)
      - BIL: (lines, bands, samples)
      - BIP: (lines, samples, bands)
    """
    with open(path, "wb") as f:
        f.write(arr.tobytes(order="C"))


def make_cube_int32(bands, lines, samples):
    """
    Build an easy-to-check cube (BSQ shape) in int32:
      band 0: zeros
      band 1: all 10
      band 2: ascending small integers
    """
    cube = np.zeros((bands, lines, samples), dtype=np.int32)
    if bands >= 2:
        cube[1, :, :] = 10
    if bands >= 3:
        cube[2, :, :] = np.arange(lines * samples, dtype=np.int32).reshape(lines, samples)
    return cube


# ------------------------
# tests
# ------------------------


def test_bsq_drop_leading_plane_when_wavelength0_zero(tmp_path):
    # small image
    samples, lines, bands = 4, 3, 3
    rci = tmp_path / "img.rci"
    hdr = tmp_path / "img.hdr"

    # Build BSQ data: band0 zeros, band1=10, band2=ramp
    cube_bsq = make_cube_int32(bands, lines, samples)  # (3,3,4)
    write_rci(rci, cube_bsq, interleave="bsq")

    # wavelengths length matches bands and starts with 0.0 => we expect to drop leading plane
    wavelengths = [0.0, 442.5, 491.1]
    write_envi_header(
        hdr,
        samples=samples,
        lines=lines,
        bands=bands,
        dtype_code=3,  # int32
        interleave="bsq",
        wavelengths=wavelengths,
    )

    reader = RCIReader(str(rci), str(hdr))
    da = reader.read()

    # Bands should be 2 after dropping the first plane
    assert da.sizes["band"] == 2
    # Wavelengths aligned to remaining bands
    assert "wavelength" in da.coords
    np.testing.assert_allclose(da["wavelength"].values, [442.5, 491.1])

    # Check data: band 1 is original band1 (all 10), band 2 is original band2 (ramp)
    np.testing.assert_array_equal(
        da.sel(band=1).values, np.full((lines, samples), 10, dtype=np.int32)
    )
    np.testing.assert_array_equal(
        da.sel(band=2).values, np.arange(lines * samples, dtype=np.int32).reshape(lines, samples)
    )


@pytest.mark.parametrize("interleave", ["bil", "bip"])
def test_interleave_bil_bip_shapes(tmp_path, interleave):
    samples, lines, bands = 4, 3, 3
    rci = tmp_path / f"img_{interleave}.rci"
    hdr = tmp_path / f"img_{interleave}.hdr"

    # Start from BSQ cube, then reshape for chosen interleave when writing
    cube_bsq = make_cube_int32(bands, lines, samples)  # (3,3,4)
    if interleave.lower() == "bil":
        raw = cube_bsq.transpose(1, 0, 2)  # (lines, bands, samples)
    else:  # bip
        raw = cube_bsq.transpose(1, 2, 0)  # (lines, samples, bands)
    write_rci(rci, raw, interleave=interleave)

    # No leading 0.0 wavelength here; keep all 3 bands
    wavelengths = [442.5, 491.1, 530.8]
    write_envi_header(
        hdr,
        samples=samples,
        lines=lines,
        bands=bands,
        dtype_code=3,
        interleave=interleave,
        wavelengths=wavelengths,
    )

    reader = RCIReader(str(rci), str(hdr))
    da = reader.read()

    # Check dims
    assert da.dims == ("band", "y", "x")
    assert da.sizes["band"] == 3
    assert da.sizes["y"] == lines
    assert da.sizes["x"] == samples

    # Spot-check a few values to ensure interleave was handled correctly
    # (band1 should be constant 10 across the image)
    np.testing.assert_array_equal(
        da.sel(band=2).values, np.full((lines, samples), 10, dtype=np.int32)
    )


def test_band_subset_and_scaling_and_dtype(tmp_path):
    samples, lines, bands = 4, 3, 3
    rci = tmp_path / "subscale.rci"
    hdr = tmp_path / "subscale.hdr"

    # Make BSQ cube; also include a 0.0 wavelength so the first plane is dropped.
    cube_bsq = make_cube_int32(bands, lines, samples)
    write_rci(rci, cube_bsq, interleave="bsq")

    wavelengths = [0.0, 500.0, 600.0]
    write_envi_header(
        hdr,
        samples=samples,
        lines=lines,
        bands=bands,
        dtype_code=3,
        interleave="bsq",
        wavelengths=wavelengths,
    )

    # Request only the second remaining band (which was original band2, the ramp)
    # Also scale by 10, and cast to uint8 (0..255)
    reader = RCIReader(
        str(rci),
        str(hdr),
        scale_factor=10.0,
        out_bands=[2],  # after drop, bands are [1,2]; band 2 is the ramp
        out_dtype="uint8",
    )
    da = reader.read()

    # After drop -> 2 bands; after subset -> 1 band
    assert da.sizes["band"] == 1
    assert da.dtype == np.uint8

    # Values are normalized to 0..255; check range only (exact values depend on min/max)
    v = da.values
    assert v.min() >= 0
    assert v.max() <= 255


def test_size_mismatch_raises(tmp_path):
    """
    Deliberately write fewer bytes than the header declares -> should raise ValueError.
    """
    samples, lines, bands = 4, 3, 3
    rci = tmp_path / "bad.rci"
    hdr = tmp_path / "bad.hdr"

    # Only write two bands worth of data (int32), but header claims 3
    cube_2 = make_cube_int32(2, lines, samples)  # (2,3,4)
    write_rci(rci, cube_2, interleave="bsq")

    write_envi_header(
        hdr,
        samples=samples,
        lines=lines,
        bands=bands,  # says 3, but file has 2
        dtype_code=3,
        interleave="bsq",
        wavelengths=[0.0, 440.0, 490.0],
    )

    with pytest.raises(ValueError, match="File size .* != expected .*"):
        _ = RCIReader(str(rci), str(hdr))
