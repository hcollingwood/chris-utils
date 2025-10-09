from __future__ import annotations

import csv
import datetime as dt
import math
from typing import Any, Dict, Mapping, Optional

import numpy as np
import pyproj
from osgeo import osr


def conv_coords(inx, iny, insrs, outsrs):
    transform = osr.CoordinateTransformation(insrs, outsrs)
    originX, originY, _ = transform.TransformPoint(inx, iny)
    return originX, originY


def gpstime2datetime(gweek, gsecs):
    gdays = float(gsecs) / 86400.0
    jd = (
        dt.datetime(1980, 1, 6, 0, 0, 0)
        + dt.timedelta(days=float(gweek) * 7.0)
        + dt.timedelta(days=gdays)
    )
    return jd.strftime("%j"), jd.strftime("%H-%M-%S")


def geo_utm_epsg_from_lonlat(lon: float, lat: float) -> int:
    zone = int(math.floor((lon + 180.0) / 6.0) + 1)
    return (326 if lat >= 0 else 327) * 100 + zone


def geo_affine_from_center(
    east: float, north: float, width: int, height: int, xres: float, yres: float
) -> tuple[float, float, float, float, float, float]:
    originX = east - (xres * (width / 2.0))
    originY = north + (yres * (height / 2.0))
    return (originX, xres, 0.0, originY, 0.0, -yres)


def geo_build_xy_coords(
    gt: tuple[float, float, float, float, float, float], width: int, height: int
):
    a, b, c, d, e, f = gt
    x = a + b * np.arange(width, dtype="float64")
    y = d + f * np.arange(height, dtype="float64")
    return x, y


def geo_grid_mapping_attrs(epsg: int) -> Dict[str, Any]:
    return {
        "grid_mapping_name": "transverse_mercator",
        "spatial_ref": f"EPSG:{epsg}",
        "epsg_code": f"EPSG:{epsg}",
    }


def geo_extract_center_lat_lon_gsd(
    chris_meta: Mapping[str, str],
) -> tuple[Optional[float], Optional[float], float]:
    lon = chris_meta.get("Longitude")
    lat = chris_meta.get("Lattitude") or chris_meta.get("Latitude")
    try:
        lonf = float(str(lon).strip())
        latf = float(str(lat).strip())
    except Exception:
        lonf = latf = None
    try:
        mode = int(str(chris_meta.get("CHRIS Mode")).strip())
    except Exception:
        mode = None
    gsd = 36.0 if mode == 1 else 18.0
    return lonf, latf, gsd


def geo_flip_using_gps(
    arr, hdr_txt_path: str | None, gps_file: str | None, centre_times_file: str | None
):
    """
    Apply the original 180° rotation logic if GPS/centre-times are available.
    No EOPF/xarray deps. Expects arr shaped (bands, y, x); returns possibly-flipped arr.
    Silently no-op on any parsing issue or if files are missing.
    """
    if not (gps_file and centre_times_file):
        return arr

    from .hdr_parser import parse_chris_hdr_txt

    try:
        meta = parse_chris_hdr_txt(hdr_txt_path) if hdr_txt_path else {}
        # year filter from "Image Date (yyyy-mm-dd)"
        ystr = str(meta.get("Image Date (yyyy-mm-dd)", ""))[:4]
        year_filter = ystr if len(ystr) == 4 else None

        # Read first and last rows from GPS file for that year
        firstrow = lastrow = None
        with open(gps_file, "r") as f:
            r = csv.reader(f, delimiter="\t")
            seen = 0
            for row in r:
                if not row:
                    continue
                if year_filter and (year_filter not in "".join(row)):
                    continue
                if seen == 0:
                    firstrow = row
                    seen = 1
                else:
                    lastrow = row
        if not (firstrow and lastrow):
            return arr

        ecef2geo = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:4326")
        slat, slon, _ = ecef2geo.transform(
            float(firstrow[3].strip()), float(firstrow[5].strip()), float(firstrow[7].strip())
        )
        elat, elon, _ = ecef2geo.transform(
            float(lastrow[3].strip()), float(lastrow[5].strip()), float(lastrow[7].strip())
        )
        descending = slat > elat

        # image index from "Image No x of y" (e.g. "1 of 5")
        img_txt = meta.get("Image No x of y")
        try:
            image_idx = int(str(img_txt).split()[0])
        except Exception:
            image_idx = 1

        need_flip = (not descending and image_idx in (1, 3, 5)) or (
            descending and image_idx in (2, 4)
        )
        if need_flip:
            # rot 180° on (y, x)
            return np.flip(arr, axis=(1, 2))
        return arr
    except Exception:
        return arr


def geo_epsg_from_da(da) -> int | None:
    """
    Extract EPSG integer from da.attrs['spatial_ref'] if present (e.g. 'EPSG:32612').
    Returns None if not parseable.
    """
    epsg_str = da.attrs.get("spatial_ref")
    if isinstance(epsg_str, str) and epsg_str.upper().startswith("EPSG:"):
        try:
            return int(epsg_str.split(":")[1])
        except Exception:
            return None
    return None


def geo_constant_geometry_arrays(da, chris_meta: dict) -> dict[str, np.ndarray]:
    """
    Build constant geometry layers (sza/oza/oaa/saa) as HxW float32 arrays
    using values from CHRIS hdr.txt. Returns {name: ndarray} for those available.
    """
    H, W = int(da.sizes["y"]), int(da.sizes["x"])

    # normalize keys once (match your _norm_keys behavior in eopf_utils)
    def _nk(d):
        import re

        return {re.sub(r"\s+", " ", k).strip().lower(): v for k, v in d.items()}

    cm = _nk(chris_meta)
    names = {
        "sza": cm.get("solar zenith angle"),
        "oza": cm.get("observation zenith angle"),
        "oaa": cm.get("observation azimuth angle"),
        "saa": cm.get("solar azimuth angle"),
    }
    out = {}
    for k, v in names.items():
        if v is None:
            continue
        try:
            out[k] = np.full((H, W), float(v), dtype="float32")
        except Exception:
            pass
    return out
