import binascii
import os
import argparse
import logging
import shutil

from chris_utils.safe.safe_measurement_metadata_xml_generator import Schema
from chris_utils.safe.safe_metadata_xml_generator import XFDU


def calculate_checksum(data: str) -> str:
    """Uses CRC-16 checksums"""
    crc = binascii.crc_hqx(data.encode("utf-8"), 0xFFFF)

    return f"{crc:04X}"  # 4 hexadecimal characters


def make_file_metadata(paths: list) -> str:
    """Generates metadata"""

    metadata = XFDU(data_objects=paths)

    return metadata.to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True
    ).decode("utf-8")


def write_metadata(metadata: str, path: str) -> None:
    """Writes metadata to manifest.xml in a given directory"""
    with open(f"{path}/manifest.xml", "w") as f:
        f.write(metadata)


def copy_mos_file(output_file_path) -> None:
    """Copies mos-object-types.xsd file"""
    mos_file_name = "mos-object-types.xsd"
    shutil.copy(f"chris_utils/safe/{mos_file_name}", f"{output_file_path}/{mos_file_name}")


def make_safe(inputs: str, output: str = '.', package_type:str=None, mode:str="1", file_class:str="OPER", sat_id="PR1"):
    """Generates SAFE archive for specified input file(s)"""

    if not os.path.exists(output):
        os.makedirs(output)

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
            valid_package_types = [
                "RPI-BAS",
                "RPI-DAT",
                "RPI-MTD",
                "COL-MTD",
                "DAT-PRD",
                "DAT-AUX",
            ]
            if package_type not in valid_package_types:
                raise Exception(
                    f"Package type {package_type} not in {valid_package_types}"
                )
            package_type_tag = f"_{package_type}"

        metadata = make_file_metadata(paths)

        checksum = calculate_checksum(metadata)

        if os.path.isabs(file):
            output_root = f"{output}/{file.split('/')[-1]}"
        else:
            output_root = f"{output}/{file}"

        output_file_path = f"{output_root}{package_type_tag}_{checksum}.SAFE"

        logging.info(packaging_message, output_file_path)

        if not os.path.exists(output_file_path):
            os.makedirs(output_file_path)

        write_metadata(metadata, output_file_path)
        for path in paths:
            file_name = path.split("/")[-1]
            shutil.copy(path, f"{output_file_path}/{file_name}")
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

            with open(f"{output_file_path}/{file_name}.xsd", "w") as f:
                f.write(measurement_xml)
            print(file_name)

            copy_mos_file(output_file_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EO-SIP")
    parser.add_argument("--inputs", help="list of input files", default=None)
    parser.add_argument("--sat_id", help="satellite identifier", default="PR1")
    parser.add_argument("--file_class", help="file class", default="OPER")
    parser.add_argument("--mode", help="mode", default="1")
    parser.add_argument("--output", help="output folder", default=".")
    parser.add_argument("--package_type", help="type of package", default=None)
    args, unknown = parser.parse_known_args()

    make_safe(inputs=args.inputs, output=args.output, package_type=args.package_type, mode=args.mode, file_class=args.file_class, sat_id=args.sat_id)
