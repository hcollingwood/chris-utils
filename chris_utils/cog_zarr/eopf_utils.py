import logging
import os
import re
from datetime import datetime, timedelta

import eopf.common.constants as constants
from eopf import EOConfiguration
from eopf.product import EOGroup, EOProduct, EOVariable
from eopf.store.cog import EOCogStore
from eopf.store.zarr import EOZarrStore

from .hdr_parser import build_eopf_root_attrs, extract_gain_table, parse_chris_hdr_txt

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


def _build_eopf_product(
    da, envi_header, hdr_txt_path, product_name=None, product_format: str | None = None
):
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
    _meta_with_table = parse_chris_hdr_txt(hdr_txt_path, keep_spectral_table=True)

    # Derive start/end datetime from centre time, mode and number of lines
    centre_iso = root_attrs.get("datetime")  # ISO centre time
    # Mode (int): "CHRIS Mode" in txt, else None
    mode_txt = _norm_keys(chris_meta).get("chris mode")
    try:
        _mode_num = int(mode_txt)
    except (TypeError, ValueError):
        _mode_num = None
    # Line integration time (μs): M1=4.2, M2–M5=2.1
    _lit_us = 4.2 if _mode_num == 1 else 2.1
    # Number of lines: prefer txt (“No of Ground Lines”), else ENVI "lines"
    try:
        _n_lines = int(chris_meta.get("No of Ground Lines") or envi_header.get("lines") or 0)
    except Exception:
        _n_lines = 0
    _start_iso = _end_iso = None
    if centre_iso and _n_lines > 0:
        try:
            _centre_dt = datetime.strptime(centre_iso, "%Y-%m-%dT%H:%M:%SZ")
            _duration_s = (_n_lines * _lit_us) / 1e6
            _half = timedelta(seconds=_duration_s / 2.0)
            _start_iso = (_centre_dt - _half).strftime("%Y-%m-%dT%H:%M:%SZ")
            _end_iso = (_centre_dt + _half).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
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
        "platform": root_attrs.get("platform"),
        "instrument": root_attrs.get("instrument"),
    }
    # DO NOT ADD start/end/centre yet; waiting for precise spreadsheet
    # if _start_iso:
    #     props["start_datetime"] = _start_iso
    # if _end_iso:
    #     props["end_datetime"] = _end_iso
    # if centre_iso:
    #     props["centre_datetime"] = centre_iso
    product.attrs["stac_discovery"] = {"properties": props}

    # merge ENVI header + EOPF root attrs
    product.attrs.update(envi_header)
    product.attrs.update(root_attrs)

    # Attach spectral table (WLLOW/WLHIGH/...)
    if table := _meta_with_table.get("spectral_table"):
        product.attrs["spectral_table"] = table

    if gains := extract_gain_table(hdr_txt_path):
        product.attrs["gain_table"] = gains

    product.attrs.pop("wavelength", None)

    # product-level measurement
    product.attrs["measurement"] = "radiance"
    if units:
        product.attrs["measurement:units"] = units

    # Authoritative band count after any plane drop/selection
    product.attrs["bands"] = int(da.sizes["band"])

    # Container-aware replacements and cleanup
    if product_format:
        # Explicitly declare container type and data layout
        pf = product_format.upper()
        product.attrs["file_type"] = "COG" if pf == "COG" else "ZARR"
        product.attrs["dtype"] = str(da.dtype)
        product.attrs["bit_depth"] = 10
        try:
            product.attrs["product_bit_depth"] = int(getattr(da.dtype, "itemsize", 0) * 8)
        except Exception:
            pass

    # Remove ENVI-only / redundant keys if present (avoid duplication)
    for k in (
        "sensor type",
        "header offset",
        "byte order",
        "file type",
        "data type",
        "chris_no_of_bands_followed_by_band_position_of_smear",
        "product_type",
        "platform",
        "instrument",
        "datetime",  # kept in stac_discovery
        "chris_sensor_type",
        "chris_mask_key_information",
        "chris_image_date_yyyy_mm_dd_",
        "chris_gain_setting",
        "chris_calculated_image_centre_time",
        "chris_no_of_samples",
        "chris_no_of_ground_lines",
        "chris_longitude",
        "chris_lattitude",
    ):
        product.attrs.pop(k, None)

    # Normalize a couple of CHRIS txt keys
    if "chris_statement_of_data_rights" in product.attrs:
        product.attrs["data_rights"] = product.attrs.pop("chris_statement_of_data_rights")
    if "chris_target_name" in product.attrs:
        product.attrs["target_name"] = product.attrs.pop("chris_target_name")

    return product, base


def write_eopf_zarr(da, envi_header, hdr_txt_path, out_zarr_path):
    """Write an EOPF-compliant Zarr store."""
    product_name = os.path.splitext(os.path.basename(out_zarr_path))[0]
    product, _ = _build_eopf_product(
        da, envi_header, hdr_txt_path, product_name, product_format="ZARR"
    )

    parent, leaf = os.path.split(out_zarr_path)
    os.makedirs(parent or ".", exist_ok=True)

    with EOZarrStore(url=parent or ".").open(mode=constants.OpeningMode.CREATE_OVERWRITE) as store:
        store[product.name] = product


def write_eopf_cog(da, envi_header, hdr_txt_path, out_cog_dir):
    """Write an EOPF-compliant COG directory (ending in .cog)."""
    # Build the EOProduct and determine the resolution group
    product_name = os.path.splitext(os.path.basename(out_cog_dir))[0]
    product, base = _build_eopf_product(
        da, envi_header, hdr_txt_path, product_name, product_format="COG"
    )

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
