# tests/conftest.py
import os
from pathlib import Path

import numpy as np
import pytest


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
