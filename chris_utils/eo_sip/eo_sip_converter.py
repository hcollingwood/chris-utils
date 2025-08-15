import argparse
import io
import os
import logging
import zipfile
from datetime import datetime
import xarray as xr

import numpy as np
from PIL import Image
import pandas as pd

import rasterio
from rasterio.errors import RasterioError

from chris_utils.eo_sip.information_xml_generator import SIPInfo
from chris_utils.eo_sip.metadata_xml_generator import EarthObservation
from chris_utils.utils import get_list_of_files

# from information_xml_generator import SIPInfo
# from metadata_xml_generator import EarthObservation
# from chris_utils.utils import get_list_of_files

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


def process_cog(path):
    with rasterio.open(path) as dataset:
        metadata = dataset.meta
        print(metadata)
        # print(dataset.profile)
        # data = metadata.read(1) ## band 1
        # views = dataset.overviews(1)

        # r_band, g_band, b_band = get_bands(metadata.coords["wavelength"].values)
        r_band, g_band, b_band = 1, 2, 3
        # import sys;sys.exit()

        # view = views[-1]
        # thumbnail_r = dataset.read(1, out_shape=(1, int(dataset.height // view), int(dataset.width // view)))
        # thumbnail_g = dataset.read(1, out_shape=(1, int(dataset.height // view), int(dataset.width // view)))
        # thumbnail_b = dataset.read(1, out_shape=(1, int(dataset.height // view), int(dataset.width // view)))

        thumbnail_r = dataset.read(r_band)
        thumbnail_g = dataset.read(g_band)
        thumbnail_b = dataset.read(b_band)

        thumbnail_rgb = make_rgb_thumbnail(thumbnail_r, thumbnail_g, thumbnail_b)


        data_file_name = path.split('/')[-1]
        file_data = open(path, 'rb').read()

        return dataset, metadata, thumbnail_rgb, [(data_file_name, file_data)]


def process_zarr_old(path):
    # path1 = "/home/hcollingwood/Documents/Code/eo-sip-converter/3FB1Image.zarr"
    contents = xr.open_zarr(path)

    metadata = contents["data"]

    r_band, g_band, b_band = get_band_numbers(metadata.coords["wavelength"].values)

    df = contents.to_dataframe().reset_index()
    # print(df)
    thumbnail_data_r = df[df.band == r_band].filter(items=['x', 'y', 'data'])
    thumbnail_data_g = df[df.band == g_band].filter(items=['x', 'y', 'data'])
    thumbnail_data_b = df[df.band == b_band].filter(items=['x', 'y', 'data'])

    thumbnail_r = thumbnail_data_r.pivot(index='y', columns='x', values='data').to_numpy()
    thumbnail_g = thumbnail_data_g.pivot(index='y', columns='x', values='data').to_numpy()
    thumbnail_b = thumbnail_data_b.pivot(index='y', columns='x', values='data').to_numpy()

    thumbnail_rgb = make_rgb_thumbnail(thumbnail_r, thumbnail_g, thumbnail_b)

    data = contents

    file_data = []
    file_root = '/'.join(path.rsplit('/')[:-1])
    for path, dirs, files in os.walk(path):
        for file in files:
            file_path = f"{path}/{file}"
            if os.path.isfile(file_path):
                binary_data = open(file_path, 'rb').read()
                file_data.append([file_path.replace(file_root, ""), binary_data])

    return data, metadata, thumbnail_rgb, file_data


def process_zarr(path):
    contents = xr.open_datatree(path, engine="zarr")

    metadata = contents.attrs

    r_band, g_band, b_band = get_band_numbers(metadata["wavelength"])

    longest_group = max(contents.groups)
    d = contents.to_dict()

    df = pd.DataFrame()
    for band in list(d[longest_group].data_vars):
        df[band] = d['/measurements/reflectance/r18m'].data_vars[band].to_dataframe()
    df = df.reset_index()

    r_column = df.columns[r_band]
    g_column = df.columns[g_band]
    b_column = df.columns[b_band]

    logging.info(f'Generating image with bands {r_column}, {g_column} and {b_column}')

    thumbnail_data_r = df[['x', 'y', r_column]]
    thumbnail_data_g = df[['x', 'y', g_column]]
    thumbnail_data_b = df[['x', 'y', b_column]]

    thumbnail_r = thumbnail_data_r.pivot(index='y', columns='x', values=r_column).to_numpy()
    thumbnail_g = thumbnail_data_g.pivot(index='y', columns='x', values=g_column).to_numpy()
    thumbnail_b = thumbnail_data_b.pivot(index='y', columns='x', values=b_column).to_numpy()

    thumbnail_rgb = make_rgb_thumbnail(thumbnail_r, thumbnail_g, thumbnail_b)

    file_data = []
    file_root = '/'.join(path.rsplit('/')[:-1])
    for path, dirs, files in os.walk(path):
        for file in files:
            file_path = f"{path}/{file}"
            if os.path.isfile(file_path):
                binary_data = open(file_path, 'rb').read()
                file_data.append([file_path.replace(file_root, ""), binary_data])

    return contents, metadata, thumbnail_rgb, file_data


def process_safe(path):


    file_data = []
    file_root = '/'.join(path.rsplit('/')[:-1])
    for path, dirs, files in os.walk(path):
        for file in files:
            file_path = f"{path}/{file}"
            if os.path.isfile(file_path):
                binary_data = open(file_path, 'rb').read()
                file_data.append([file_path.replace(file_root, ""), binary_data])

    return file_data




def make_rgb_thumbnail(thumbnail_r, thumbnail_g, thumbnail_b):
    return np.stack([thumbnail_r, thumbnail_g, thumbnail_b], axis=-1)

def get_band_numbers(wavelengths):
    red_band = get_band_number("red", wavelengths)
    green_band = get_band_number("green", wavelengths)
    blue_band = get_band_number("blue", wavelengths)
    return red_band, green_band, blue_band

def get_band_number(colour, wavelengths):
    minimum, maximum = all_wavelengths[colour]
    valid_bands = []
    for i, band in enumerate(wavelengths):
        if minimum <= band <= maximum:
            valid_bands.append([i, band])

    valid_bands = sorted(valid_bands, key=lambda x: x[1])  # sort bands by wavelength
    # choose index from middle of list
    index = len(valid_bands) // 2
    return valid_bands[index][0]



def generate_metadata(file_identifier, data=None, metadata: dict=None, image=None, report=None):


    xml = EarthObservation(id=file_identifier).to_xml(
        pretty_print=True,
        encoding='UTF-8',
        standalone=True
    )

    return xml


def generate_info(file_identifier):
    parent_instance = SIPInfo(version="2.0", sip_creator="ESA", sip_creation_time=datetime(2021, 2, 3))

    xml = parent_instance.to_xml(
        pretty_print=False,
        encoding='UTF-8',
        standalone=True
    )

    return xml


def get_version(root):
    version = 1
    while True:
        padded_number = f"{version:0>4}"

        file = f"{root}_{padded_number}.ZIP"
        if os.path.exists(file):
            version += 1
        else:
            return padded_number

def write_to_file(data, file_name):
    with open(file_name, 'w') as f:
        f.write(data)

def make_image(data, file_name):
    im = Image.fromarray(data, mode="RGB")
    im.save(file_name)


def get_image(image):
    image = (image * 255).astype(np.uint8)
    img_byte_arr = io.BytesIO()
    im = Image.fromarray(image)
    im.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


def convert_eo_sip(inputs: str, output: str='.', version:str=None, extras:str=None, mode:str="1", sat_id: str="PR1", file_class:str="OPER"):

    if not os.path.exists(output):
        os.makedirs(output)

    files = get_list_of_files(inputs.split(','))
    for file in files:
        logging.info(f"Processing {file}")
        if file.lower().endswith('.zarr'):  # try as ZARR
            raw_data, metadata, image, file_data = process_zarr(file)
        elif file.lower().endswith('.tif'):  # try as COG
            raw_data, metadata, image, file_data = process_cog(file)
        else:
            raise Exception("File type not recognised")

        if extras and os.path.isdir(extras) and extras.endswith('.SAFE'):
            file_data = process_safe(extras)

        product_type = mode_to_product_type[mode.lower()]

        file_name_root = f'{sat_id}_{file_class}_{product_type}_20100328T011431_N01-800_W078-260'
        version = version if version else get_version(file_name_root)
        file_name = f'{file_name_root}_{version}'

        metadata = generate_metadata(file_name, raw_data, metadata=metadata, image=image)
        info = generate_info(file_name)
        image_data = get_image(image)

        image_file_name = f"{file_name}.BI.PNG"
        metadata_file_name = f"{file_name}.MD.XML"
        information_file_name = f"{file_name}.SI.XML"
        zip_file_name = f"{output}/{file_name}.ZIP"

        logging.info(f"Writing to {zip_file_name}")
        with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zip:
            zip.writestr(image_file_name, image_data)
            zip.writestr(metadata_file_name, metadata)
            zip.writestr(information_file_name, info)
            for name, data in file_data:
                zip.writestr(name, data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EO-SIP')
    parser.add_argument('--inputs', help='list of input files', default=None)
    parser.add_argument("--sat_id", help="satellite identifier", default="PR1")
    parser.add_argument("--file_class", help="file class", default="OPER")
    parser.add_argument("--mode", help="mode", default="1")
    parser.add_argument("--output", help="output folder", default=".")
    parser.add_argument("--extras", help="additional files", default=None)
    args, unknown = parser.parse_known_args()

    convert_eo_sip(inputs=args.inputs, output=args.output, extras=args.extras, mode=args.mode, file_class=args.file_class, sat_id=args.sat_id)
