import logging
import os
import re

import eopf.common.constants as constants
from eopf import EOConfiguration
from eopf.product import EOGroup, EOProduct, EOVariable
from eopf.store.cog import EOCogStore
from eopf.store.zarr import EOZarrStore

from .hdr_parser import build_eopf_root_attrs, parse_chris_hdr_txt

EOConfiguration().logging__level = "DEBUG"
EOConfiguration().logging__dask_level = "DEBUG"


def _norm_keys(d: dict) -> dict:
    """Convert key to lowercase and normalize internal whitespace"""
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
    """Return radiance units. Prefer the CHRIS/EOPF field if present; otherwise fall back to ENVI key"""
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
