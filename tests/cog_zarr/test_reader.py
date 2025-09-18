from pathlib import Path

import numpy as np
import pytest

from chris_utils.cog_zarr.reader import RCIReader


@pytest.fixture
def make_cube_int32():
    """
    Factory that builds an easy-to-check cube in int32 with BSQ shape (bands, lines, samples):
      band 0: zeros
      band 1: all 10
      band 2: ascending small integers
    """

    def _make(bands, lines, samples):
        cube = np.zeros((bands, lines, samples), dtype=np.int32)
        if bands >= 2:
            cube[1, :, :] = 10
        if bands >= 3:
            cube[2, :, :] = np.arange(lines * samples, dtype=np.int32).reshape(lines, samples)
        return cube

    return _make


@pytest.fixture
def write_envi_header(tmp_path: Path):
    """
    Factory that writes a minimal ENVI header and returns its path.
    """

    def _write(
        fname: str,
        *,
        samples: int,
        lines: int,
        bands: int,
        dtype_code: int = 3,  # 3 = int32
        interleave: str = "bsq",
        wavelengths=None,
        byte_order: int = 0,
    ) -> Path:
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
        path = tmp_path / fname
        path.write_text(txt, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_rci(tmp_path: Path):
    """
    Factory that writes an .rci binary file for the given array and returns its path.
    The array must already be in the desired interleave layout.
    """

    def _write(fname: str, arr: np.ndarray) -> Path:
        path = tmp_path / fname
        path.write_bytes(arr.tobytes(order="C"))
        return path

    return _write


@pytest.fixture
def rci_with_hdr(tmp_path: Path, make_cube_int32, write_envi_header, write_rci):
    """
    Factory that creates a paired (rci, hdr) with controllable interleave & wavelengths.
    Returns (rci_path, hdr_path, cube_bsq) where cube_bsq is the original BSQ cube.
    """

    def _create(
        *,
        samples: int,
        lines: int,
        bands: int,
        interleave: str = "bsq",
        dtype_code: int = 3,
        wavelengths=None,
        byte_order: int = 0,
        rci_name: str = "img.rci",
        hdr_name: str = "img.hdr",
    ):
        # build canonical BSQ cube
        cube_bsq = make_cube_int32(bands, lines, samples)

        # convert layout for writing if needed
        interleave = interleave.lower()
        if interleave == "bsq":
            raw = cube_bsq
        elif interleave == "bil":
            raw = cube_bsq.transpose(1, 0, 2)  # (lines, bands, samples)
        elif interleave == "bip":
            raw = cube_bsq.transpose(1, 2, 0)  # (lines, samples, bands)
        else:
            raise ValueError(f"Unsupported interleave in fixture: {interleave}")

        rci = write_rci(rci_name, raw)
        hdr = write_envi_header(
            hdr_name,
            samples=samples,
            lines=lines,
            bands=bands,
            dtype_code=dtype_code,
            interleave=interleave,
            wavelengths=wavelengths or [],
            byte_order=byte_order,
        )
        return rci, hdr, cube_bsq

    return _create


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
