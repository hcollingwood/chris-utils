import logging
import os
import re

import eopf.common.constants as constants
import numpy as np
import rasterio
from eopf import EOConfiguration
from eopf.product import EOGroup, EOProduct, EOVariable
from eopf.store.cog import EOCogStore
from eopf.store.zarr import EOZarrStore
from rasterio.env import Env
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

from .hdr_parser import build_eopf_root_attrs, parse_chris_hdr_txt

EOConfiguration().logging__level = "DEBUG"
EOConfiguration().logging__dask_level = "DEBUG"


def _norm_keys(d: dict) -> dict:
    # Lowercase keys and normalize internal whitespace
    return {re.sub(r"\s+", " ", k).strip().lower(): v for k, v in d.items()}


def _gsd_from_mode(chris_meta: dict) -> int:
    """Return nominal GSD (metres) from 'CHRIS Mode' in metadata.

    Mode 1 → 36 m; any other (2-5) or missing/invalid → 18 m.
    """
    mode_val = _norm_keys(chris_meta).get("chris mode")
    try:
        mode_num = int(mode_val)
    except (TypeError, ValueError):
        return 18
    return 36 if mode_num == 1 else 18


def _radiance_units(envi_header: dict, root_attrs: dict) -> str | None:
    # Prefer the CHRIS/EOPF field if present; otherwise fall back to ENVI key
    return (
        root_attrs.get("chris_calibration_data_units")
        or envi_header.get("calibration data units")
        or envi_header.get("chris_calibration_data_units")
    )


def _build_eopf_product(da, envi_header, hdr_txt_path, product_name=None):
    """
    Build and return an EOProduct populated with:
      - Groups
            measurements/
                image/
                y, x
                oa01_radiance, oa02_radiance, ...
    """
    # parse CHRIS metadata & EOPF root attrs
    chris_meta = parse_chris_hdr_txt(hdr_txt_path)
    root_attrs = build_eopf_root_attrs(chris_meta, hdr_txt_path)

    # determine GSD (18 or 36)
    gsd = _gsd_from_mode(chris_meta)
    logging.info(f"CHRIS operating in mode {gsd}")
    base = "measurements/image"

    # if caller gave us a product_name, use that; otherwise fallback to hdr stem
    if product_name:
        name = product_name
    else:
        _, leaf = os.path.split(hdr_txt_path)
        name = os.path.splitext(leaf)[0]

    # start building
    product = EOProduct(name=name)
    product["measurements"] = EOGroup()
    product[base] = EOGroup()

    # coords
    product[f"{base}/y"] = EOVariable(data=da["y"].values, dims=("y",))
    product[f"{base}/x"] = EOVariable(data=da["x"].values, dims=("x",))

    # pick up units if present (e.g. "microWatts/nm/m^2/str") and wavelength
    units = _radiance_units(envi_header, root_attrs)
    has_wl = "wavelength" in da.coords

    # one variable per band
    for idx, bi in enumerate(da["band"].values, start=1):
        vname = f"oa{idx:02d}_radiance"  # CPM naming
        arr2d = da.sel(band=bi).values
        var = EOVariable(data=arr2d, dims=("y", "x"))
        # annotate measurement + units (+ wavelength if available)
        var.attrs["measurement"] = "radiance"
        if units:
            var.attrs["units"] = units
        if has_wl:
            try:
                var.attrs["wavelength_nm"] = float(da["wavelength"].sel(band=bi))
            except Exception:
                pass
        product[f"{base}/{vname}"] = var

    # minimal STAC discovery
    props = {
        "product:type": root_attrs.get("product_type"),
        "start_datetime": root_attrs.get("datetime"),
        "platform": root_attrs.get("platform"),
        "instrument": root_attrs.get("instrument"),
    }
    product.attrs["stac_discovery"] = {"properties": props}

    # merge ENVI header + EOPF root attrs
    product.attrs.update(envi_header)
    product.attrs.update(root_attrs)

    # product-level measurement
    product.attrs["measurement"] = "radiance"
    if units:
        product.attrs["measurement:units"] = units

    return product, base


def _maskify_singleband_tif_inplace(path: str, nodata_value=0, profile_name="deflate"):
    """
    Rewrites a single-band GeoTIFF at `path` as a proper COG with:
      - dataset-level nodata = nodata_value
      - INTERNAL dataset mask (0=nodata, 255=data)
    """
    tmp = path + ".tmp.tif"

    with rasterio.open(path) as src:
        data = src.read(1)
        prof = src.profile.copy()
        # write a tiled temp GTiff and set dataset nodata
        prof.update(tiled=True, blockxsize=512, blockysize=512, nodata=nodata_value)

        # Build validity mask (treat zeros as nodata; tighten if you need)
        if np.issubdtype(data.dtype, np.floating):
            eps = max(1e-6, float(np.finfo(data.dtype).eps) * 10.0)
            valid = np.abs(data) > eps
        else:
            valid = data != nodata_value

        with Env(GDAL_TIFF_INTERNAL_MASK="YES"):
            with rasterio.open(tmp, "w", **prof) as dst:
                dst.write(data, 1)
                dst.write_mask(valid.astype("uint8") * 255)
                # preserve tags if present
                try:
                    tags = src.tags()
                    if tags:
                        dst.update_tags(**tags)
                except Exception:
                    pass

    # Translate temp to final COG, preserving mask and nodata
    dst_prof = cog_profiles[profile_name].copy()
    dst_prof["nodata"] = nodata_value
    with Env(GDAL_TIFF_INTERNAL_MASK="YES", GDAL_NUM_THREADS="ALL_CPUS"):
        cog_translate(
            tmp,
            path,
            dst_prof,
            add_mask=True,
            nodata=nodata_value,
            in_memory=False,
            quiet=True,
        )

    # Clean up temp and any stray sidecars
    try:
        os.remove(tmp)
        for side in (tmp + ".msk", path + ".msk"):
            if os.path.exists(side):
                os.remove(side)
    except Exception:
        pass


def _maskify_all_cogs_in_eopf_dir(eopf_cog_dir: str, nodata_value=0):
    """Walk the EOPF .cog directory and maskify every *.tif in-place."""
    for root, _, files in os.walk(eopf_cog_dir):
        for fn in files:
            if fn.lower().endswith(".tif"):
                _maskify_singleband_tif_inplace(os.path.join(root, fn), nodata_value=nodata_value)


def write_eopf_zarr(da, envi_header, hdr_txt_path, out_zarr_path):
    """Write an EOPF-compliant Zarr store."""
    product_name = os.path.splitext(os.path.basename(out_zarr_path))[0]
    product, _ = _build_eopf_product(da, envi_header, hdr_txt_path, product_name)

    parent, leaf = os.path.split(out_zarr_path)
    os.makedirs(parent or ".", exist_ok=True)

    with EOZarrStore(url=parent or ".").open(mode=constants.OpeningMode.CREATE_OVERWRITE) as store:
        store[product.name] = product


def write_eopf_cog(da, envi_header, hdr_txt_path, out_cog_dir):
    """Write an EOPF-compliant COG directory (ending in .cog)."""
    # Build the EOProduct and determine the resolution group
    product_name = os.path.splitext(os.path.basename(out_cog_dir))[0]
    product, base = _build_eopf_product(da, envi_header, hdr_txt_path, product_name)

    # Ensure the output .cog directory exists
    os.makedirs(out_cog_dir, exist_ok=True)

    # Write each level of the hierarchy explicitly
    with EOCogStore(url=out_cog_dir).open(mode=constants.OpeningMode.CREATE_OVERWRITE) as store:
        # 1) Root attrs.json
        store[""] = product

        # 2) measurements group folder + its attrs
        store["measurements"] = product["measurements"]

        # 3) radiance subgroup folder + its attrs
        store[base] = product[base]

    # post-process: embed internal mask + nodata=0 for each per-band TIFF
    _maskify_all_cogs_in_eopf_dir(out_cog_dir, nodata_value=0)
