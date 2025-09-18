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
    # Lowercase keys and normalize internal whitespace
    return {re.sub(r"\s+", " ", k).strip().lower(): v for k, v in d.items()}


def _build_eopf_product(da, envi_header, hdr_txt_path, product_name=None):
    """
    Build and return an EOProduct populated with:
      - Groups measurements → reflectance → r{gsd}m
      - x/y coords
      - one EOVariable per band
      - merged attrs (ENVI + EOPF root + minimal STAC discovery)
    """
    # parse CHRIS metadata & EOPF root attrs
    chris_meta = parse_chris_hdr_txt(hdr_txt_path)
    root_attrs = build_eopf_root_attrs(chris_meta, hdr_txt_path)

    # determine GSD (18 or 36)
    norm = _norm_keys(chris_meta)
    mode_str = norm.get("chris mode")
    try:
        mode = int(mode_str) if mode_str is not None else 2
    except (TypeError, ValueError):
        mode = 2
    gsd = 36 if mode == 1 else 18
    res_grp = f"measurements/reflectance/r{gsd}m"

    # if caller gave us a product_name, use that; otherwise fallback to hdr stem
    if product_name:
        name = product_name
    else:
        _, leaf = os.path.split(hdr_txt_path)
        name = os.path.splitext(leaf)[0]

    # start building
    product = EOProduct(name=name)
    product["measurements"] = EOGroup()
    product["measurements/reflectance"] = EOGroup()
    product[res_grp] = EOGroup()

    # coords
    product[f"{res_grp}/y"] = EOVariable(data=da["y"].values, dims=("y",))
    product[f"{res_grp}/x"] = EOVariable(data=da["x"].values, dims=("x",))

    # one variable per band
    for bi in da["band"].values:
        bname = f"b{int(bi):02d}"
        arr2d = da.sel(band=bi).values
        product[f"{res_grp}/{bname}"] = EOVariable(
            data=arr2d,
            dims=("y", "x"),
        )

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

    return product, res_grp


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
    product, res_grp = _build_eopf_product(da, envi_header, hdr_txt_path, product_name)

    # Ensure the output .cog directory exists
    os.makedirs(out_cog_dir, exist_ok=True)

    # Write each level of the hierarchy explicitly
    with EOCogStore(url=out_cog_dir).open(mode=constants.OpeningMode.CREATE_OVERWRITE) as store:
        # 1) Root attrs.json
        store[""] = product

        # 2) measurements group folder + its attrs
        store["measurements"] = product["measurements"]

        # 3) reflectance subgroup folder + its attrs
        store["measurements/reflectance"] = product["measurements/reflectance"]

        # 4) the r{gsd}m folder, which will write one TIFF per band
        store[res_grp] = product[res_grp]
