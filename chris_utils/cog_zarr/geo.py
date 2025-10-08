from __future__ import annotations

import datetime as dt
import math
from typing import Any, Dict, Mapping, Optional

import numpy as np
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
