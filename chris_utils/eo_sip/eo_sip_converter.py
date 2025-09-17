import argparse
import calendar
import io
import json
import logging
import math
import os
import re
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from PIL import Image

from chris_utils.eo_sip.information_xml_generator import SIPInfo
from chris_utils.eo_sip.metadata_xml_generator import EarthObservation
from chris_utils.utils import get_list_of_files, get_version

mode_to_product_type = {
    "1": "CHR_MO1_1P",
    "2": "CHR_MO2_1P",
    "3": "CHR_MO3_1P",
    "4": "CHR_MO4_1P",
    "5": "CHR_MO5_1P",
    "hrc": "HRC_HRC_1P",
}

all_wavelengths = {
    "red": [625, 750],
    "green": [495, 570],
    "blue": [400, 495],
}


def sin_deg(angle):
    return math.sin(math.radians(angle))


def cos_deg(angle):
    return math.cos(math.radians(angle))


def asin_deg(angle):
    return math.degrees(math.sin(angle))


def acos_deg(angle):
    return math.degrees(math.cos(angle))


def check_metadata(metadata: dict):
    regex_checks = {
        "chris_lattitude": r"[-]?\d+.\d+",
        "chris_longitude": r"[-]?\d+.\d+",
        "chris_chris_mode": r"([1-5]|hrc)",
        "chris_image_date_yyyy_mm_dd_": r"[A-z0-9-\s]+",
        "chris_calculated_image_centre_time": r"[A-z0-9-:\s]+",
    }
    list_checks = {
        "wavelength": float,
    }

    numeric_string_checks = {"chris_lattitude": [-90, 90], "chris_longitude": [-180, 180]}
    datetime_string_checks = {
        "chris_image_date_yyyy_mm_dd_": "%Y-%m-%d",
        "chris_calculated_image_centre_time": "%H:%M:%S",
    }

    missing_values = set()
    invalid_values = set()

    for key in regex_checks.keys():
        if not metadata.get(key):
            missing_values.add(key)
            break

        try:
            if not re.match(f"^{regex_checks[key]}$", metadata[key]):
                invalid_values.add(key)
        except TypeError:
            invalid_values.add(key)

    for key in list_checks.keys():
        if not metadata.get(key):
            missing_values.add(key)
            break

        var_type = list_checks[key]
        try:
            if not all([type(x) == var_type for x in metadata[key]]):
                invalid_values.add(key)

        except ValueError:
            invalid_values.add(key)

    for key in numeric_string_checks.keys():
        if not metadata.get(key):
            missing_values.add(key)
            break

        min_value, max_value = numeric_string_checks[key]
        value = metadata[key]
        try:
            if type(value) is not str:
                invalid_values.add(key)
                break
            value = float(value)
            if not min_value <= value <= max_value:
                invalid_values.add(key)

        except ValueError:
            invalid_values.add(key)

    for key in datetime_string_checks.keys():
        if not metadata.get(key):
            missing_values.add(key)
            break

        try:
            datetime.strptime(metadata[key], datetime_string_checks[key])
        except ValueError:
            invalid_values.add(key)

    if missing_values:
        raise Exception(f"Missing metadata entries identified: {missing_values}")
    if invalid_values:
        raise Exception(f"Invalid metadata identified: {invalid_values}")


# def process_cog_old(path):
#     with rasterio.open(path) as dataset:
#         metadata = dataset.meta
#         # print(metadata)
#         # print(dataset.profile)
#         # data = metadata.read(1) ## band 1
#         # views = dataset.overviews(1)
#
#         # r_band, g_band, b_band = get_bands(metadata.coords["wavelength"].values)
#         r_band, g_band, b_band = 1, 2, 3
#         # import sys;sys.exit()
#
#         # view = views[-1]
#         # thumbnail_r = dataset.read(1, out_shape=(1, int(dataset.height // view), int(dataset.width // view)))
#         # thumbnail_g = dataset.read(1, out_shape=(1, int(dataset.height // view), int(dataset.width // view)))
#         # thumbnail_b = dataset.read(1, out_shape=(1, int(dataset.height // view), int(dataset.width // view)))
#
#         thumbnail_r = dataset.read(r_band)
#         thumbnail_g = dataset.read(g_band)
#         thumbnail_b = dataset.read(b_band)
#
#         thumbnail_rgb = make_rgb_thumbnail(thumbnail_r, thumbnail_g, thumbnail_b)
#
#
#         data_file_name = path.split('/')[-1]
#         file_data = open(path, 'rb').read()
#
#         return dataset, metadata, thumbnail_rgb, [(data_file_name, file_data)]


def process_cog(path):
    with open(f"{path}/attrs.json") as f:
        metadata = json.load(f)
    check_metadata(metadata)

    r_band, g_band, b_band = get_band_indexes(metadata["wavelength"])

    longest_group, _, files = max(os.walk(path))
    files = sorted([file for file in files if file.endswith(".tif")])

    red_file = files[r_band]
    green_file = files[g_band]
    blue_file = files[b_band]

    with rasterio.open(f"{longest_group}/{red_file}") as dataset:
        thumbnail_r = dataset.read(1)
    with rasterio.open(f"{longest_group}/{green_file}") as dataset:
        thumbnail_g = dataset.read(1)
    with rasterio.open(f"{longest_group}/{blue_file}") as dataset:
        thumbnail_b = dataset.read(1)

    scaled_thumbnail_r, scaled_thumbnail_g, scaled_thumbnail_b = normalise_image(
        [thumbnail_r, thumbnail_g, thumbnail_b]
    )

    thumbnail_rgb = make_rgb_thumbnail(scaled_thumbnail_r, scaled_thumbnail_g, scaled_thumbnail_b)

    file_data = []
    file_root = "/".join(path.rsplit("/")[:-1])
    for root_path, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root_path, file)
            if os.path.isfile(file_path):
                binary_data = open(file_path, "rb").read()
                file_data.append([file_path.replace(file_root, ""), binary_data])

    data = 3
    # TODO: find how this is generated / what needs to be in it, remove if needed
    return data, metadata, thumbnail_rgb, file_data


def normalise_image(bands: list):

    # normalise everything together
    # min_value = min([band.min() for band in bands])
    # bands = [band - min_value for band in bands]
    #
    # new_max_value = max([band.max() for band in bands])
    # bands = [(1 / new_max_value) * band for band in bands]
    #
    # lo = min([np.quantile(band, 0.001) for band in bands])
    # hi = max([np.quantile(band, 0.999) for band in bands])
    # # lo = min([np.quantile(band, 0.02) for band in bands])
    # # hi = max([np.quantile(band, 0.98) for band in bands])
    # bands = [(((band - lo) / (hi - lo)).clip(0, 1).astype("float32")) for band in bands]
    #
    # return bands

    # normalise individual bands
    new_bands = []
    for band in bands:
        lo = np.quantile(band, 0.025)
        hi = np.quantile(band, 0.995)
        band = ((band - lo) / (hi - lo)).clip(0, 1).astype("float32")

        new_bands.append(band)

    return new_bands


# def process_zarr_old(path):
#     # path1 = "/home/hcollingwood/Documents/Code/eo-sip-converter/3FB1Image.zarr"
#     contents = xr.open_zarr(path)
#
#     metadata = contents["data"]
#
#     r_band, g_band, b_band = get_band_numbers(metadata.coords["wavelength"].values)
#
#     df = contents.to_dataframe().reset_index()
#     # print(df)
#     thumbnail_data_r = df[df.band == r_band].filter(items=['x', 'y', 'data'])
#     thumbnail_data_g = df[df.band == g_band].filter(items=['x', 'y', 'data'])
#     thumbnail_data_b = df[df.band == b_band].filter(items=['x', 'y', 'data'])
#
#     thumbnail_r = thumbnail_data_r.pivot(index='y', columns='x', values='data').to_numpy()
#     thumbnail_g = thumbnail_data_g.pivot(index='y', columns='x', values='data').to_numpy()
#     thumbnail_b = thumbnail_data_b.pivot(index='y', columns='x', values='data').to_numpy()
#
#     thumbnail_rgb = make_rgb_thumbnail(thumbnail_r, thumbnail_g, thumbnail_b)
#
#     data = contents
#
#     file_data = []
#     file_root = '/'.join(path.rsplit('/')[:-1])
#     for path, dirs, files in os.walk(path):
#         for file in files:
#             file_path = f"{path}/{file}"
#             if os.path.isfile(file_path):
#                 binary_data = open(file_path, 'rb').read()
#                 file_data.append([file_path.replace(file_root, ""), binary_data])
#
#     return data, metadata, thumbnail_rgb, file_data


def process_zarr(path):
    contents = xr.open_datatree(path, engine="zarr")

    metadata = contents.attrs
    check_metadata(metadata)

    r_band, g_band, b_band = get_band_indexes(metadata["wavelength"])

    longest_group = max(contents.groups)

    d = contents.to_dict()

    df = pd.DataFrame()
    for band in list(d[longest_group].data_vars):
        df[band] = d[longest_group].data_vars[band].to_dataframe()
    df = df.reset_index()

    # +2 added to skip the x and the y columns
    r_column = df.columns[r_band + 2]
    g_column = df.columns[g_band + 2]
    b_column = df.columns[b_band + 2]

    logging.info(f"Generating image with bands {r_column}, {g_column} and {b_column}")

    thumbnail_data_r = df[["x", "y", r_column]]
    thumbnail_data_g = df[["x", "y", g_column]]
    thumbnail_data_b = df[["x", "y", b_column]]

    thumbnail_r = thumbnail_data_r.pivot(index="y", columns="x", values=r_column).to_numpy()
    thumbnail_g = thumbnail_data_g.pivot(index="y", columns="x", values=g_column).to_numpy()
    thumbnail_b = thumbnail_data_b.pivot(index="y", columns="x", values=b_column).to_numpy()

    scaled_thumbnail_r, scaled_thumbnail_g, scaled_thumbnail_b = normalise_image(
        [thumbnail_r, thumbnail_g, thumbnail_b]
    )
    thumbnail_rgb = make_rgb_thumbnail(scaled_thumbnail_r, scaled_thumbnail_g, scaled_thumbnail_b)
    # thumbnail_rgb = make_rgb_thumbnail(thumbnail_r, thumbnail_g, thumbnail_b)

    file_data = []
    file_root = "/".join(path.rsplit("/")[:-1])
    for root_path, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root_path, file)
            if os.path.isfile(file_path):
                binary_data = open(file_path, "rb").read()
                file_data.append([file_path.replace(file_root, ""), binary_data])

    return contents, metadata, thumbnail_rgb, file_data


def process_safe(folder_path):
    file_data = []
    file_root = "/".join(folder_path.rsplit("/")[:-1])
    for path, _, files in os.walk(folder_path):
        for file in files:
            file_path = f"{path}/{file}"
            if os.path.isfile(file_path):
                binary_data = open(file_path, "rb").read()
                file_data.append([file_path.replace(file_root, ""), binary_data])

    return file_data


def make_rgb_thumbnail(thumbnail_r, thumbnail_g, thumbnail_b):
    return np.stack([thumbnail_r, thumbnail_g, thumbnail_b], axis=-1)


def get_band_indexes(wavelengths):
    red_band = get_band_index("red", wavelengths)
    green_band = get_band_index("green", wavelengths)
    blue_band = get_band_index("blue", wavelengths)
    return red_band, green_band, blue_band


def get_band_index(colour, wavelengths):
    minimum, maximum = all_wavelengths[colour]
    valid_bands = []
    for i, band in enumerate(wavelengths):
        if minimum <= band <= maximum:
            valid_bands.append([i, band])

    if not valid_bands:
        raise ValueError(
            f"No {colour} band in {minimum}-{maximum} nm; available: {list(wavelengths)}"
        )

    closest_matching_wavelength = min(
        valid_bands, key=lambda x: abs(x[1] - (minimum + maximum) / 2)
    )

    return closest_matching_wavelength[0]


def generate_metadata(file_identifier, data=None, metadata: dict = None, image=None, report=None):
    # TODO: check inputs and update/remove if not needed
    xml = EarthObservation(id=file_identifier, data=metadata).to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True
    )

    return xml


def generate_info(file_identifier):
    parent_instance = SIPInfo(version="2.0", sip_creator="ESA", sip_creation_time=datetime.now())

    xml = parent_instance.to_xml(pretty_print=False, encoding="UTF-8", standalone=True)

    return xml


# def get_version(root, output_folder="."):
#     version = 1
#     while True:
#         padded_number = f"{version:0>4}"
#
#         file = f"{output_folder}/{root}_{padded_number}.ZIP"
#         if os.path.exists(file):
#             version += 1
#         else:
#             return padded_number


def write_to_file(data, file_name):
    with open(file_name, "w") as f:
        f.write(data)


def make_image(data, file_name):
    im = Image.fromarray(data, mode="RGB")
    im.save(file_name)


def get_image(image):
    image = (image * 255).astype(np.uint8)
    img_byte_arr = io.BytesIO()
    im = Image.fromarray(image, mode="RGB")
    im.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


def format_latitude(raw: str) -> str:
    # raw_decimal_degrees, raw_degrees = math.modf(raw)  # splits at decimal point
    # abs = math.fabs(raw_degrees)
    # abs_decimal = math.fabs(raw_decimal_degrees*1000)  # turn decimal into integer

    # hemisphere = 'S' if float(raw_degrees) < 0 else 'N'
    # degrees = "{:2.0f}".format(int(raw_degrees))
    # decimal_degrees = "{0:03d}".format(int(raw_decimal_degrees))
    raw_degrees, raw_decimal_degrees = raw.split(".")
    decimal_degrees = int(float(f"0.{raw_decimal_degrees}") * 1000)

    if float(raw_degrees) < 0:
        hemisphere = "S"
        raw_degrees = raw_degrees[1:]
    else:
        hemisphere = "N"
    degrees = f"{int(raw_degrees):02}"
    decimal_degrees = f"{decimal_degrees:03}"

    return f"{hemisphere}{degrees}-{decimal_degrees}"


def format_longitude(raw: str) -> str:
    # raw_decimal_degrees, raw_degrees = math.modf(raw)  # splits at decimal point
    # abs = math.fabs(raw_degrees)
    # abs_decimal = math.fabs(raw_decimal_degrees*1000)  # turn decimal into integer
    #
    # hemisphere = 'W' if raw_degrees < 0 else 'E'
    # degrees = "{:3.0f}".format(abs)
    # decimal_degrees = "{:3.0f}".format(abs_decimal)

    raw_degrees, raw_decimal_degrees = raw.split(".")
    decimal_degrees = int(float(f"0.{raw_decimal_degrees}") * 1000)

    if float(raw_degrees) < 0:
        hemisphere = "W"
        raw_degrees = raw_degrees[1:]
    else:
        hemisphere = "E"
    degrees = f"{raw_degrees:03}"
    decimal_degrees = f"{decimal_degrees:03}"

    return f"{hemisphere}{degrees}-{decimal_degrees}"


def generate_file_name(metadata) -> str:
    """Generates a file name from the provided metadata"""

    return f'{metadata["sat_id"]}_{metadata["file_class"]}_{metadata["product_type"]}_{metadata["formatted_timestamp"]}_{metadata["formatted_latitude"]}_{metadata["formatted_longitude"]}'


def get_file_size(path):
    if os.path.isfile(path):
        total_size = os.path.getsize(path)
    else:
        total_size = 0
        for root_path, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root_path, file)
                if not os.path.islink(file_path):
                    total_size += os.path.getsize(file_path)

    return total_size


def calculate_angles(metadata):
    # illumination_azimuth_angle = "46.11*"  # astropy
    # illumination_elevation_angle = "61.47*"  # solar zenith angle

    """
    Equations from here:
    https://www.pveducation.org/pvcdrom/properties-of-sunlight/declination-angle
    https://www.pveducation.org/pvcdrom/properties-of-sunlight/azimuth-angle
    https://www.pveducation.org/pvcdrom/properties-of-sunlight/elevation-angle
    https://gml.noaa.gov/grad/solcalc/solareqns.PDF
    """

    timestamp = metadata["timestamp"]
    latitude = float(metadata["chris_latitude"])
    longitude = float(metadata["chris_longitude"])

    day_of_year = int(timestamp.strftime("%j"))
    days_in_year = 366 if calendar.isleap(timestamp.year) else 365
    fraction_of_year = (2 * math.pi / days_in_year) * (day_of_year - 1 + (timestamp.hour - 12) / 24)

    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(fraction_of_year)
        - 0.032077 * math.sin(fraction_of_year)
        - 0.014615 * math.cos(2 * fraction_of_year)
        - 0.040849 * math.sin(2 * fraction_of_year)
    )

    declination_rad = (
        0.006918
        - 0.399912 * math.cos(fraction_of_year)
        + 0.070257 * math.sin(fraction_of_year)
        - 0.006758 * math.cos(2 * fraction_of_year)
        + 0.000907 * math.sin(2 * fraction_of_year)
        - 0.002697 * math.cos(3 * fraction_of_year)
        + 0.00148 * math.sin(3 * fraction_of_year)
    )
    declination_deg = math.degrees(declination_rad)

    time_offset = equation_of_time + 4 * longitude

    true_solar_time = timestamp.hour * 60 + timestamp.minute + timestamp.second / 60 + time_offset

    solar_hour_angle = true_solar_time / 4 - 180

    zenith_deg = acos_deg(
        sin_deg(latitude) * sin_deg(declination_deg)
        + cos_deg(latitude) * cos_deg(declination_deg) * cos_deg(solar_hour_angle)
    )
    # azimuth_rad = math.acos ((math.sin(dec_rad)*cos(lat_rad) - cos(dec)*sin(lat_rad)*cos(solar_hour_angle))/cos(elevation_rad))
    azimuth_deg = 180 - acos_deg(
        -(sin_deg(latitude) * cos_deg(zenith_deg) - sin_deg(declination_deg))
        / (cos_deg(latitude) * sin_deg(zenith_deg))
    )

    elevation_deg = 90 + latitude - declination_deg

    return azimuth_deg, elevation_deg


def convert_eo_sip(
    inputs: str,
    output: str = ".",
    extras: str = None,
    sat_id: str = "PR1",
    file_class: str = "OPER",
):

    if not os.path.exists(output):
        os.makedirs(output)

    files = get_list_of_files(inputs.split(","))
    for file in files:
        logging.info(f"Processing {file}")
        if file.lower().endswith(".zarr"):  # try as ZARR
            raw_data, raw_metadata, image, file_data = process_zarr(file)
        elif file.lower().endswith(".cog"):  # try as COG
            raw_data, raw_metadata, image, file_data = process_cog(file)
        else:
            raise Exception("File type not recognised")

        if extras and os.path.isdir(extras) and extras.endswith(".SAFE"):
            file_data = process_safe(extras)  # overwrite Zarr/COG file data - not needed for SAFE

        file_size = get_file_size(file)

        # TODO: verify that all the required inputs are in the metadata file

        raw_metadata["chris_latitude"] = raw_metadata["chris_lattitude"]

        raw_metadata["file_size"] = file_size

        raw_metadata["sat_id"] = sat_id
        raw_metadata["file_class"] = file_class
        raw_metadata["product_type"] = mode_to_product_type[
            raw_metadata["chris_chris_mode"].lower()
        ]
        raw_metadata["formatted_latitude"] = format_latitude(raw_metadata["chris_latitude"])
        raw_metadata["formatted_longitude"] = format_longitude(raw_metadata["chris_longitude"])

        timestamp = datetime.strptime(
            f"{raw_metadata['chris_image_date_yyyy_mm_dd_']} {raw_metadata['chris_calculated_image_centre_time']}",
            "%Y-%m-%d %H:%M:%S",
        )
        raw_metadata["timestamp"] = timestamp
        raw_metadata["formatted_timestamp"] = timestamp.strftime("%Y%m%dT%H%M%S")
        file_name_root = generate_file_name(raw_metadata)

        raw_metadata["illumination_azimuth_angle"], raw_metadata["illumination_elevation_angle"] = (
            calculate_angles(raw_metadata)
        )

        version = get_version(file_name_root, ".ZIP", output)
        file_name = f"{file_name_root}_{version}"

        xml_metadata = generate_metadata(file_name, raw_data, metadata=raw_metadata, image=image)
        xml_info = generate_info(file_name)
        image_data = get_image(image)

        image_file_name = f"{file_name}.BI.PNG"
        metadata_file_name = f"{file_name}.MD.XML"
        information_file_name = f"{file_name}.SI.XML"
        zip_file_name = f"{output}/{file_name}.ZIP"

        logging.info(f"Writing to {zip_file_name}")
        with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zip:
            zip.writestr(image_file_name, image_data)
            zip.writestr(metadata_file_name, xml_metadata)
            zip.writestr(information_file_name, xml_info)
            for name, data in file_data:
                zip.writestr(name, data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EO-SIP")
    parser.add_argument("inputs", nargs=1, help="list of input files")
    parser.add_argument("--sat_id", help="satellite identifier", default="PR1")
    parser.add_argument("--file_class", help="file class", default="OPER")
    parser.add_argument("--output", help="output folder", default=".")
    parser.add_argument("--extras", help="additional files", default=None)
    args, unknown = parser.parse_known_args()

    convert_eo_sip(
        inputs=args.inputs[0],
        output=args.output,
        extras=args.extras,
        file_class=args.file_class,
        sat_id=args.sat_id,
    )
