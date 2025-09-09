import json
import os

import numpy as np
import rasterio
import xarray as xr
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

from .header import parse_envi_header

ENVI_DTYPE_MAP = {
    1: "uint8",
    2: "int16",
    3: "int32",
    4: "float32",
    5: "float64",
    12: "uint16",
    13: "uint32",
    14: "int64",
    15: "uint64",
}


class RCIReader:
    def __init__(self, rci_path, hdr_path, *, scale_factor=None, out_bands=None, out_dtype=None):
        self.rci_path = rci_path
        self.header = parse_envi_header(hdr_path)

        # Required header fields
        for k in ("samples", "lines", "bands", "data type"):
            if k not in self.header:
                raise KeyError(f"Missing '{k}' in header.")

        # Determine numpy dtype
        endian = "<" if self.header.get("byte order", 0) == 0 else ">"
        code = int(self.header["data type"])
        base = ENVI_DTYPE_MAP.get(code)
        if not base:
            raise ValueError(f"Unsupported ENVI data type code: {code}")
        dt = np.dtype(base).newbyteorder(endian)
        self.dtype = dt

        # Dimensions
        self.width = int(self.header["samples"])
        self.height = int(self.header["lines"])
        self.bands = int(self.header["bands"])
        self.interleave = self.header.get("interleave", "bsq").upper()
        offset = int(self.header.get("header offset", 0))

        # Verify file size matches
        size = os.path.getsize(self.rci_path) - offset
        expected = self.width * self.height * self.bands * dt.itemsize
        if size != expected:
            # try alternate data types
            for alt_code, alt_str in ENVI_DTYPE_MAP.items():
                alt_dt = np.dtype(alt_str).newbyteorder(endian)
                if size == self.width * self.height * self.bands * alt_dt.itemsize:
                    print(
                        f"Warning: file size {size} bytes matches dtype {alt_str}, not {base}. Using {alt_str}."
                    )
                    self.dtype = alt_dt
                    break
            else:
                raise ValueError(
                    f"File size {size} != expected {expected} "
                    f"(width*height*bands*itemsize). "
                    f"hdr bands={self.bands}, dtype={self.dtype}"
                )

        # Geo metadata placeholders
        self.transform = self.header.get("map info")
        self.crs = self.header.get("coordinate system string")  # we don't have this at the moment

        # Optional processing params
        self.scale_factor = scale_factor
        self.out_bands = out_bands
        self.out_dtype = out_dtype

        self.da = None

    def read(self) -> xr.DataArray:
        # Load raw binary
        count = self.width * self.height * self.bands
        raw = np.fromfile(self.rci_path, dtype=self.dtype, count=count)

        # Reshape according to interleave
        if self.interleave == "BSQ":
            arr = raw.reshape((self.bands, self.height, self.width))
        elif self.interleave == "BIL":
            arr = raw.reshape((self.height, self.bands, self.width)).transpose(1, 0, 2)
        elif self.interleave == "BIP":
            arr = raw.reshape((self.height, self.width, self.bands)).transpose(2, 0, 1)
        else:
            raise ValueError(f"Unsupported interleave: {self.interleave}")

        # Build DataArray with wavelength coordinate
        coords = {
            "band": np.arange(1, self.bands + 1),
            "y": np.arange(self.height),
            "x": np.arange(self.width),
        }

        # Grab the full wavelength list from the header
        all_wavelengths = self.header.get("wavelength")
        if isinstance(all_wavelengths, (list, tuple)) and len(all_wavelengths) >= self.bands:
            # Attach the full list now; xarray will slice it if we subset bands later.
            coords["wavelength"] = ("band", all_wavelengths[: self.bands])

        da = xr.DataArray(
            arr,
            dims=("band", "y", "x"),
            coords=coords,
            attrs=self.header,
        )

        # Band subset
        if self.out_bands:
            da = da.sel(band=self.out_bands)

        # Scale reflectance
        if self.scale_factor:
            da = da.astype("float32") / self.scale_factor

        # Cast to output dtype
        if self.out_dtype:
            tgt = np.dtype(self.out_dtype)
            if np.issubdtype(tgt, np.integer):
                data = da.values.astype("float32")
                data_range = data.max() - data.min()
                if data_range == 0:
                    # avoid NaNs when image is constant
                    arr2 = np.zeros_like(data, dtype=tgt)
                else:
                    arr2 = ((data - data.min()) / data_range * np.iinfo(tgt).max).astype(tgt)
            else:
                arr2 = da.values.astype(tgt)
            da = xr.DataArray(arr2, dims=da.dims, coords=da.coords, attrs=da.attrs)

        self.da = da
        return da

    def to_zarr(self, zarr_path, chunks=None, **kwargs) -> str:
        if chunks is None:
            chunks = {"band": 1, "y": 512, "x": 512}
        if self.da is None:
            self.read()

        ds = self.da.to_dataset(name="data")

        # Disable all chunk‐level compression
        encoding = {name: {"compressor": None} for name in list(ds.data_vars) + list(ds.coords)}

        # Write a Zarr v2 store (raw codec) with consolidated metadata
        ds.chunk(chunks).to_zarr(
            zarr_path,
            mode="w",
            encoding=encoding,
            consolidated=True,
            zarr_format=2,
            **kwargs,
        )
        return zarr_path

    def to_cog(self, cog_path, profile_name="deflate", config=None, **kwargs) -> str:
        if self.da is None:
            self.read()

        tmp = cog_path + ".tmp.tif"
        profile = {
            "driver": "GTiff",
            "height": self.da.sizes["y"],
            "width": self.da.sizes["x"],
            "count": self.da.sizes["band"],
            "dtype": str(self.da.dtype),
            "crs": self.crs,
            "transform": self.transform,
        }
        with rasterio.open(tmp, "w", **profile) as dst:
            for i in range(self.da.sizes["band"]):
                dst.write(self.da.values[i], i + 1)
            # Embed wavelengths as JSON metadata
            wls = self.header.get("wavelength")
            if wls is not None:
                try:
                    dst.update_tags(
                        wavelengths=json.dumps([float(v) for v in np.asarray(wls).tolist()])
                    )
                except Exception:
                    pass

        dst_profile = cog_profiles[profile_name]
        cog_translate(
            tmp,
            cog_path,
            dst_profile,
            config=config or {"GDAL_NUM_THREADS": "ALL_CPUS"},
            in_memory=False,
            quiet=True,
            **kwargs,
        )
        os.remove(tmp)
        return cog_path
