import argparse
import binascii
import datetime
import logging
import os
import shutil
import tempfile
import zipfile

from chris_utils.safe.safe_measurement_metadata_xml_generator import Schema
from chris_utils.safe.mos_file_generator import Schema as MosSchema
from chris_utils.safe.safe_metadata_xml_generator import XFDU

valid_package_types = [
    "RPI-BAS",
    "RPI-DAT",
    "RPI-MTD",
    "COL-MTD",
    "DAT-PRD",
    "DAT-AUX",
]


def calculate_crc_checksum(data: str) -> str:
    """Uses CRC-16 checksums"""
    crc = binascii.crc_hqx(data.encode("utf-8"), 0xFFFF)

    return f"{crc:04X}"  # 4 hexadecimal characters


def make_manifest(paths: list=None) -> str:
    """Generates manifest"""

    manifest = XFDU(data_objects=paths)

    return manifest.to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True
    ).decode("utf-8")


def make_metadata(timestamp: datetime.datetime) -> str:
    """Generates metadata"""

    metadata = MosSchema(timestamp=timestamp)

    return metadata.to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True
    ).decode("utf-8")


def write_index(metadata: str, path: str) -> None:
    """Writes metadata to mos-object-types.xml in a given directory"""
    with open(f"{path}/mos-object-types.xml", "w") as f:
        f.write(metadata)

def write_manifest(metadata: str, path: str) -> None:
    """Writes metadata to manifest.xml in a given directory"""
    with open(f"{path}/manifest.xml", "w") as f:
        f.write(metadata)


def copy_mos_file(output_file_path) -> None:
    """Copies mos-object-types.xsd file"""
    mos_file_name = "mos-object-types.xsd"
    shutil.copy(f"chris_utils/safe/{mos_file_name}", f"{output_file_path}/{mos_file_name}")


def make_safe(
    inputs: str,
    timestamp: datetime.datetime,
    output: str = ".",
    package_type: str = None,
    mode: str = "1",
    file_class: str = "OPER",
    sat_id="PR1",
):
    """Generates SAFE archive for specified input file(s)"""

    # TODO: update/remove any unused input variables
    if not os.path.exists(output):
        os.makedirs(output)

    zip_name = 'ZIP.zip'

    processing_message = "Processing %s"
    packaging_message = "Packaging %s"
    input_files = inputs.split(",")
    for file in input_files:
        logging.info(processing_message, file)

        paths = []
        for root, dirs, files in os.walk(file):
            for f in files:
                paths.append(os.path.join(root, f))

        package_type_tag = ""
        if package_type := package_type:
            if package_type not in valid_package_types:
                raise Exception(f"Package type {package_type} not in {valid_package_types}")
            package_type_tag = f"_{package_type}"

        manifest = make_manifest([zip_name])
        metadata = make_metadata(timestamp)

        checksum = calculate_crc_checksum(manifest)

        if os.path.isabs(file):
            output_root = f"{output}/{file.split('/')[-1]}"
        else:
            output_root = f"{output}/{file}"

        output_file_path = f"{output_root}{package_type_tag}_{checksum}.SAFE"

        logging.info(packaging_message, output_file_path)

        if not os.path.exists(output_file_path):
            os.makedirs(output_file_path)

        measurement_dir = f"{output_file_path}/measurement"
        metadata_dir = f"{output_file_path}/metadata"
        documentation_dir = f"{output_file_path}/documentation"  # these are optional
        index_dir = f"{output_file_path}/index"  # these are optional
        dir_list = [measurement_dir, metadata_dir, documentation_dir, index_dir]
        for d in dir_list:
            if not os.path.exists(d):
                os.makedirs(d)

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = f"{tmp}/{zip_name}"
            with zipfile.ZipFile(zip_path, 'w') as zip:

                for path in paths:
                    zip.write(path)
                    # file_name = path.split("/")[-1]

                shutil.copy(zip_path, f"{measurement_dir}/MEASUREMENT-{zip_name}")
        measurement_xml = (
            Schema(
                target_namespace="http://www.esa.int/safe/1.2/mos",
                xmlns="http://www.esa.int/safe/1.2/mos",
            )
            .to_xml(
                pretty_print=True,
                encoding="UTF-8",
                standalone=True,
                exclude_unset=True,
            )
            .decode("utf-8")
        )

        with open(f"{metadata_dir}/zip.xsd", "w") as f:
            f.write(measurement_xml)

        # copy_mos_file(output_file_path, metadata)
        write_index(metadata, index_dir)
        write_manifest(manifest, output_file_path)

        for d in dir_list:
            if len(os.listdir(d)) == 0:
                shutil.rmtree(d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EO-SIP")
    parser.add_argument("--inputs", help="list of input files", default=None)
    parser.add_argument("--sat_id", help="satellite identifier", default="PR1")
    parser.add_argument("--file_class", help="file class", default="OPER")
    parser.add_argument("--mode", help="mode", default="1")
    parser.add_argument("--output", help="output folder", default=".")
    parser.add_argument("--package_type", help="type of package", default=None)
    args, unknown = parser.parse_known_args()

    make_safe(
        inputs=args.inputs,
        output=args.output,
        package_type=args.package_type,
        mode=args.mode,
        file_class=args.file_class,
        sat_id=args.sat_id,
    )
