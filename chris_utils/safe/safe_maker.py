import argparse
import binascii
import logging
import os
import re
import shutil
import tempfile

from chris_utils.eo_sip import process_cog, process_zarr
from chris_utils.safe.metadata_config import (
    dat_schema,
    hdr_schema,
    set_schema,
    txt_schema,
)
from chris_utils.safe.measurement_metadata_generator import Schema as MosSchema
from chris_utils.safe.manifest_xml_generator import XFDU
from chris_utils.utils import get_version

valid_package_types = [
    "RPI-BAS",
    "RPI-DAT",
    "RPI-MTD",
    "COL-MTD",
    "DAT-PRD",
    "DAT-AUX",
]

xml_schemas = {
    "dat": dat_schema(),
    "txt": txt_schema(),
    "hdr": hdr_schema(),
    "set": set_schema(),
}


def calculate_crc_checksum(data: str) -> str:
    """Uses CRC-16 checksums"""
    crc = binascii.crc_hqx(data.encode("utf-8"), 0xFFFF)

    return f"{crc:04X}"  # 4 hexadecimal characters


def make_manifest(paths: list = None) -> str:
    """Generates manifest"""

    manifest = XFDU(data_objects=paths)

    return manifest.to_xml(pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True).decode(
        "utf-8"
    )


def make_xsd(file_type: str) -> str:
    """Generates metadata"""

    metadata = MosSchema(file_type=file_type)

    return metadata.to_xml(pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True).decode(
        "utf-8"
    )


def write_index(metadata: str, path: str) -> None:
    """Writes metadata to mos-object-types.xml in a given directory"""
    with open(f"{path}/mos-object-types.xml", "w") as f:
        f.write(metadata)


def write_manifest(metadata: str, path: str) -> None:
    """Writes metadata to manifest.xml in a given directory"""
    with open(f"{path}/MANIFEST.XML", "w") as f:
        f.write(metadata)


def generate_file_name(metadata_file, suffix, output_dir):
    if metadata_file.endswith(".zarr"):
        _, metadata, _, _ = process_zarr(metadata_file)
    elif metadata_file.endswith(".cog"):
        _, metadata, _, _ = process_cog(metadata_file)
    elif type(metadata_file) is dict:
        metadata = metadata_file
        if not (
            "chris_image_date_yyyy_mm_dd_" in metadata.keys()
            and "chris_calculated_image_centre_time" in metadata.keys()
        ):
            raise Exception(
                "Required metadata not available. Needs chris_image_date_yyyy_mm_dd_ and "
                "chris_calculated_image_centre_time"
            )
    else:
        raise Exception("File type not recognised")

    timestamp = (
        metadata["chris_image_date_yyyy_mm_dd_"] + "T" + metadata["chris_calculated_image_centre_time"]
    )

    root = f"CHRIS_{re.sub('[^0-9a-zA-Z]+', '', timestamp)}"

    version = get_version(root, suffix, output_dir)

    return f"{root}_{version}{suffix}"


def make_safe(
    inputs: str,
    metadata: str,
    output: str = ".",
    package_type: str = None,
):
    """Generates SAFE archive for specified input file(s)"""

    if not os.path.exists(output):
        os.makedirs(output)

    file_types = set()
    all_paths = []

    processing_message = "Processing %s"
    packaging_message = "Packaging %s"
    input_files = inputs.split(",")
    for file in input_files:
        logging.info(processing_message, file)

        paths = []
        for root, _, files in os.walk(file):
            for f in files:
                paths.append(os.path.join(root, f))

        package_type_tag = ""
        if package_type := package_type:
            if package_type not in valid_package_types:
                raise Exception(f"Package type {package_type} not in {valid_package_types}")
            package_type_tag = f"_{package_type}"

        with tempfile.TemporaryDirectory() as temp_dir:
            logging.info(packaging_message, temp_dir)

            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            measurement_dir = f"{temp_dir}/measurement"
            metadata_dir = f"{temp_dir}/metadata"
            documentation_dir = f"{temp_dir}/documentation"  # these are optional
            index_dir = f"{temp_dir}/index"  # these are optional
            dir_list = [measurement_dir, metadata_dir, documentation_dir, index_dir]

            for d in dir_list:
                if not os.path.exists(d):
                    os.makedirs(d)

            for path in paths:
                file_type = path.split(".")[-1]
                output_dat_path = f"{measurement_dir}/MEASUREMENT-{file_type}.dat"
                shutil.copy(path, output_dat_path)
                file_types.add(file_type)
                all_paths.append(output_dat_path)

            for file_type in file_types:
                try:
                    xml = (
                        xml_schemas[file_type]
                        .to_xml(
                            pretty_print=True,
                            encoding="UTF-8",
                            standalone=True,
                            exclude_unset=True,
                        )
                        .decode("utf-8")
                    )

                    output_xsd_path = f"{metadata_dir}/{file_type}.xsd"
                    with open(output_xsd_path, "w") as f:
                        f.write(xml)
                        all_paths.append(output_xsd_path)

                except KeyError:
                    logging.error(f"Schema for {file_type} not found")

            all_paths.sort()
            manifest = make_manifest(all_paths)
            checksum = calculate_crc_checksum(manifest)
            output_file_ending = f"{package_type_tag}_{checksum}.SAFE"

            output_file_name = generate_file_name(metadata, output_file_ending, output)

            output_file_path = f"{output}/{output_file_name}"

            if not os.path.exists(output_file_path):
                os.makedirs(output_file_path)

            write_manifest(manifest, output_file_path)
            shutil.copytree(temp_dir, output_file_path, dirs_exist_ok=True)

            for d in dir_list:
                if len(os.listdir(d)) == 0:
                    shutil.rmtree(d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EO-SIP")
    parser.add_argument("--inputs", help="list of input files", default=None)
    parser.add_argument("--mode", help="mode", default="1")
    parser.add_argument("--output", help="output folder", default=".")
    parser.add_argument("--package_type", help="type of package", default=None)
    parser.add_argument("--metadata", help="metadata", default=None)
    args, unknown = parser.parse_known_args()

    make_safe(
        inputs=args.inputs,
        output=args.output,
        package_type=args.package_type,
        metadata=args.metadata,
    )
