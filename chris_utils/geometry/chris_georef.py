#!/usr/bin/env python3

import argparse
import datetime as dt
import glob
import os
import shutil

import numpy as np
import pyproj
from osgeo import gdal, osr


def main():
    parser = argparse.ArgumentParser(
        description="Apply basic georeferencing (notebook logic wrapped as a script)."
    )
    parser.add_argument(
        "--site",
        choices=["Audobon", "Beijing", "Montreal", "Devecser"],
        default="Devecser",
        help="Site preset to use (default: Devecser).",
    )
    parser.add_argument(
        "--ifolder",
        default=r"C:\DDrive\Vega\Proba-reprocessing\Geometry",
        help="Folder containing TIFF and ancillary files.",
    )
    args = parser.parse_args()

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

    # Site/Mode based information - testing for:
    ## image viewing geometry order is -50 -40 0 40 50 for the (up to) 5 images
    site = args.site
    # site = "Devecser"
    if site == "Audobon":
        latv, lonv = 31.60, -110.54
        mode = 3
        yres, xres = 18, 18  # metres
        date = "040411"
        image = 1  # Read from txt file as 'Image No x of y'
        # define UTM projection, based on Sentinel-2 file being used as reference
        epsg_val = 32612  # WGS 84 / UTM zone 12N
    elif site == "Beijing":
        latv, lonv = 39.97, 116.37
        mode = 3
        yres, xres = 18, 18  # metres
        date = "070512"
        image = 1
        epsg_val = 32650
    elif site == "Montreal":
        latv, lonv = 45.53, -73.60
        mode = 1
        yres, xres = 36, 36  # metres
        date = "070502"
        image = 1
        epsg_val = 32618
    elif site == "Devecser":
        latv, lonv = 47.09194, 17.45917
        mode = 5  # Half Swath Width, so may need adjusting to account for this - To Do
        yres, xres = 18, 18  # metres
        date = "101013"
        image = 1
        epsg_val = 32633
    else:
        raise SystemExit("Unknown site")
    year = "20{}".format(date[0:2])
    print("{} Year: {}".format(site, year))

    # Setup projections
    wgs = osr.SpatialReference()
    wgs.ImportFromEPSG(int(4326))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_val)

    # Load COG file
    ifolder = args.ifolder
    cogfile = os.path.join(ifolder, "oa02_radiance.tif")
    nfile = os.path.join(ifolder, "oa02_radiance-updated.tif")

    # Copy to new version to update
    if os.path.exists(nfile):
        os.remove(nfile)
    shutil.copy(cogfile, nfile)

    # Find centre times file then open GPS file to check orbit direction
    searchstr = "*{}*{}*".format(site, date)
    ctfile = glob.glob(os.path.join(ifolder, searchstr))
    if len(ctfile) == 0:
        raise SystemExit("Could not find {} centre times file".format(searchstr))
    else:
        ref = os.path.basename(ctfile[0]).split("_")[1]
        print("Searching for {} GPS file".format(ref))
        gps_files = glob.glob(os.path.join(ifolder, "CHRIS_{}*".format(ref)))
        gfile = gps_files[0]
        print("GPS file {}".format(gfile))

        import csv

        with open(gfile, "r") as f:
            reader = csv.reader(f, delimiter="\t")
            lcount = 0
            for count, row in enumerate(reader):
                if len(row) > 0:
                    if str(year) in str(row):
                        if lcount == 0:
                            firstrow = row
                            lcount += 1
                        else:
                            lastrow = row

        print("First row: {}".format(firstrow))
        print("Last row: {}".format(lastrow))

    # Convert ECEF coords to geodetic coords
    sposx, sposy, sposz = (
        float(firstrow[3].strip()),
        float(firstrow[5].strip()),
        float(firstrow[7].strip()),
    )
    svelx, svely, svelz = (
        float(firstrow[9].strip()),
        float(firstrow[11].strip()),
        float(firstrow[13].strip()),
    )
    gtime, gweek, gsecs = (
        firstrow[0].strip(),
        float(firstrow[15].strip()),
        float(firstrow[17].strip()),
    )
    jday, gtime = gpstime2datetime(gweek, gsecs)
    print("Julian day: {} {}".format(jday, gtime))
    ecef_geod = pyproj.Transformer.from_crs("EPSG:4978", "EPSG:4326")  # ECEF to WGS
    slat, slon, salt = ecef_geod.transform(sposx, sposy, sposz)
    print(
        "ECEF[x,y,z]: {} {} {} WGS84[lon,lat,alt]: {} {} {}".format(
            sposx, sposy, sposz, slon, slat, salt
        )
    )

    gposx, gposy, gposz = (
        float(lastrow[3].strip()),
        float(lastrow[5].strip()),
        float(lastrow[7].strip()),
    )
    gvelx, gvely, gvelz = (
        float(lastrow[9].strip()),
        float(lastrow[11].strip()),
        float(lastrow[13].strip()),
    )
    elat, elon, ealt = ecef_geod.transform(gposx, gposy, gposz)

    # Convert to ECEF
    print(
        "Start[lon,lat,alt]: {} {} {} End[lon,lat,alt]: {} {} {}".format(
            slon, slat, salt, elon, elat, ealt
        )
    )
    if slat > elat:
        print("Orbit is N>S, descending")
        descending = True
    else:
        print("Orbit is S>N, ascending")
        descending = False

    # Open
    if not os.path.exists(nfile):
        raise SystemExit("Failed to copy {}".format(nfile))
    print("Opening: {}".format(nfile))
    in_ds = gdal.Open(nfile)  # Open to update
    driver = gdal.GetDriverByName("MEM")
    ds = driver.CreateCopy("", in_ds, strict=0)
    in_ds = None

    # Extract image information
    ysize, xsize = ds.RasterYSize, ds.RasterXSize
    print("Image size: {} {}".format(ysize, xsize))

    # Calculate position of top left corner in UTM coords
    midX, midY = conv_coords(latv, lonv, wgs, srs)
    print("Converted {} {} to {} {} in {}".format(latv, lonv, midY, midX, epsg_val))
    originX, originY = midX - (xres * (xsize / 2)), midY + (yres * (ysize / 2))
    print("Origin {} {}".format(originX, originY))

    # if the image is ascending then rotate the image
    ## from Lisa - images in each CHRIS sequence are collected during a kind of rocking manoeuvre, which means that alternate images in the same sequence have alternating N-S/S-N collection.
    if (not descending and (image == 1 or image == 3 or image == 5)) or (
        descending and (image == 2 or image == 4)
    ):
        darray = ds.GetRasterBand(1).ReadAsArray()
        print("Input array: {}".format(darray.shape))
        darray = np.rot90(darray, 2)
        print("Rotated output array: {}".format(darray.shape))
        ds.GetRasterBand(1).WriteArray(darray)
    else:
        print("Scene doesn't need to be rotated")

    # Set projection
    ds.SetProjection(srs.ExportToWkt())

    # Apply geotransform and save
    geotransform = [originX, xres, 0, originY, 0, -yres]
    ds.SetGeoTransform(geotransform)
    print("Geotransform: {}".format(geotransform))
    # Saving as file
    driver = gdal.GetDriverByName("GTiff")
    ds_out = driver.CreateCopy(nfile, ds, strict=0)
    ds_out = None
    print("Completed, created {}".format(nfile))


if __name__ == "__main__":
    main()
