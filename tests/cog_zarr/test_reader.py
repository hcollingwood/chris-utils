# tests/test_reader.py
import numpy as np
import pytest

from chris_utils.cog_zarr.reader import RCIReader


def test_bsq_drop_leading_plane_when_wavelength0_zero(rci_with_hdr):
    samples, lines, bands = 4, 3, 3

    rci, hdr, _cube_bsq = rci_with_hdr(
        samples=samples,
        lines=lines,
        bands=bands,
        interleave="bsq",
        wavelengths=[0.0, 442.5, 491.1],  # triggers the drop
    )

    reader = RCIReader(str(rci), str(hdr))
    da = reader.read()

    assert da.sizes["band"] == 2
    np.testing.assert_allclose(da["wavelength"].values, [442.5, 491.1])
    # band 1 is original band1 (all 10), band 2 is the ramp
    np.testing.assert_array_equal(
        da.sel(band=1).values, np.full((lines, samples), 10, dtype=np.int32)
    )
    np.testing.assert_array_equal(
        da.sel(band=2).values, np.arange(lines * samples, dtype=np.int32).reshape(lines, samples)
    )


@pytest.mark.parametrize("interleave", ["bil", "bip"])
def test_interleave_bil_bip_shapes(rci_with_hdr, interleave):
    samples, lines, bands = 4, 3, 3

    rci, hdr, _cube_bsq = rci_with_hdr(
        samples=samples,
        lines=lines,
        bands=bands,
        interleave=interleave,
        wavelengths=[442.5, 491.1, 530.8],  # keep all bands
    )

    reader = RCIReader(str(rci), str(hdr))
    da = reader.read()

    assert da.dims == ("band", "y", "x")
    assert da.sizes["band"] == 3
    assert da.sizes["y"] == lines
    assert da.sizes["x"] == samples
    # band 2 should be constant 10 across the image
    np.testing.assert_array_equal(
        da.sel(band=2).values, np.full((lines, samples), 10, dtype=np.int32)
    )


def test_band_subset_and_scaling_and_dtype(rci_with_hdr):
    samples, lines, bands = 4, 3, 3

    rci, hdr, _cube_bsq = rci_with_hdr(
        samples=samples,
        lines=lines,
        bands=bands,
        interleave="bsq",
        wavelengths=[0.0, 500.0, 600.0],  # drop leading
    )

    reader = RCIReader(
        str(rci),
        str(hdr),
        scale_factor=10.0,
        out_bands=[2],  # after drop, bands are [1,2]; band 2 is the ramp
        out_dtype="uint8",
    )
    da = reader.read()

    assert da.sizes["band"] == 1
    assert da.dtype == np.uint8
    v = da.values
    assert v.min() >= 0 and v.max() <= 255


def test_size_mismatch_raises(tmp_path, write_envi_header, write_rci, make_cube_int32):
    samples, lines, bands = 4, 3, 3

    # only 2 bands of data written but header claims 3
    cube_2 = make_cube_int32(2, lines, samples)
    rci = write_rci("bad.rci", cube_2)
    hdr = write_envi_header(
        "bad.hdr",
        samples=samples,
        lines=lines,
        bands=bands,  # says 3
        dtype_code=3,
        interleave="bsq",
        wavelengths=[0.0, 440.0, 490.0],
    )

    with pytest.raises(ValueError, match="File size .* != expected .*"):
        _ = RCIReader(str(rci), str(hdr))
