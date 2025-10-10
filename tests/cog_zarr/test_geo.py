import math

import numpy as np
import xarray as xr

from chris_utils.cog_zarr.geo import (
    geo_affine_from_center,
    geo_build_xy_coords,
    geo_constant_geometry_arrays,
    geo_epsg_from_da,
    geo_extract_center_lat_lon_gsd,
    geo_grid_mapping_attrs,
    geo_utm_epsg_from_lonlat,
)


def test_geo_utm_epsg_from_lonlat_north():
    # UTM zone for lon=-110.54 ~ zone 12N -> EPSG:32612
    epsg = geo_utm_epsg_from_lonlat(-110.54, 31.60)
    assert epsg == 32612


def test_geo_utm_epsg_from_lonlat_south():
    # Southern hemisphere (e.g., lon=12, lat=-34 -> EPSG:32733)
    epsg = geo_utm_epsg_from_lonlat(12.0, -34.0)
    assert epsg == 32733


def test_geo_affine_from_center_and_build_xy():
    east, north = 543_637.24, 3_496_191.896  # arbitrary
    width, height = 4, 3
    xres = yres = 18.0
    gt = geo_affine_from_center(east, north, width, height, xres, yres)
    # origin should be half-extent left/up from center
    originX, _, _, originY, _, neg_yres = gt
    assert math.isclose(originX, east - (xres * (width / 2.0)))
    assert math.isclose(originY, north + (yres * (height / 2.0)))
    assert neg_yres == -yres

    x, y = geo_build_xy_coords(gt, width, height)
    assert x.shape == (width,)
    assert y.shape == (height,)
    # monotonic
    assert np.all(np.diff(x) > 0)
    assert np.all(np.diff(y) < 0)  # because GT uses negative yres


def test_geo_grid_mapping_attrs():
    attrs = geo_grid_mapping_attrs(32612)
    assert attrs["spatial_ref"] == "EPSG:32612"
    assert attrs["grid_mapping_name"] == "transverse_mercator"


def test_geo_extract_center_lat_lon_gsd_mode1():
    meta = {"Longitude": "-110.54", "Lattitude": "31.60", "CHRIS Mode": "1"}
    lon, lat, gsd = geo_extract_center_lat_lon_gsd(meta)
    assert lon == -110.54 and lat == 31.60 and gsd == 36.0


def test_geo_extract_center_lat_lon_gsd_default_mode():
    meta = {"Longitude": "10.0", "Latitude": "50.0"}  # no mode
    lon, lat, gsd = geo_extract_center_lat_lon_gsd(meta)
    assert lon == 10.0 and lat == 50.0 and gsd == 18.0  # default non-mode1 -> 18


def test_geo_epsg_from_da_ok():
    da = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"), attrs={"spatial_ref": "EPSG:32612"})
    assert geo_epsg_from_da(da) == 32612


def test_geo_epsg_from_da_missing():
    da = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"))
    assert geo_epsg_from_da(da) is None


def test_geo_constant_geometry_arrays_ok():
    da = xr.DataArray(np.zeros((3, 4)), dims=("y", "x"))
    meta = {
        "Solar Zenith Angle": "45.5",
        "Observation Zenith Angle": "12.0",
        "Observation Azimuth Angle": "100.0",
        "Solar Azimuth Angle": "150.0",
    }
    out = geo_constant_geometry_arrays(da, meta)
    assert set(out.keys()) == {"sza", "oza", "oaa", "saa"}
    for arr in out.items():
        assert arr.shape == (3, 4)
        assert arr.dtype == np.float32
