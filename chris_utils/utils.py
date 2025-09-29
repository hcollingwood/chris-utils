import logging
import os
import re
from datetime import datetime


def get_list_of_files(inputs: list):
    files = []

    error_message = "%s not recognised. Ensure that path is valid"

    def process_input(i):
        # if os.path.isfile(i) and i.endswith('.cog'):
        #     files.append(i)
        #     print(i, "file")
        if os.path.isdir(i):
            if i.lower().endswith(".zarr") or i.lower().endswith(".cog"):
                files.append(i)
            elif i.endswith(".SAFE"):
                files.append(i)
            else:
                for file in os.listdir(i):
                    item_path = os.path.join(i, file)
                    process_input(item_path)
        else:
            logging.error(error_message, i)

    for i in inputs:
        process_input(i)

    return files


def get_version(root, suffix, output_folder="."):
    version = 1
    while True:
        padded_number = f"{version:0>4}"

        file = os.path.join(output_folder, f"{root}_{padded_number}{suffix}")
        if os.path.exists(file):
            version += 1
        else:
            return padded_number


def check_metadata(
    metadata: dict,
    regex_checks=None,
    list_checks=None,
    numeric_string_checks=None,
    datetime_string_checks=None,
):

    if datetime_string_checks is None:
        datetime_string_checks = {}
    if numeric_string_checks is None:
        numeric_string_checks = {}
    if list_checks is None:
        list_checks = {}
    if regex_checks is None:
        regex_checks = {}
    missing_values = set()
    invalid_values = set()

    for key in regex_checks.keys():
        if not metadata.get(key):
            missing_values.add(key)

        try:
            if not re.match(f"^{regex_checks[key]}$", metadata[key]):
                invalid_values.add(key)
        except TypeError:
            invalid_values.add(key)

    for key in list_checks.keys():
        if not metadata.get(key):
            missing_values.add(key)

        var_type = list_checks[key]
        try:
            if not all([type(x) == var_type for x in metadata[key]]):
                invalid_values.add(key)

        except ValueError:
            invalid_values.add(key)

    for key in numeric_string_checks.keys():
        if not metadata.get(key):
            missing_values.add(key)

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

        try:
            datetime.strptime(metadata[key], datetime_string_checks[key])
        except ValueError:
            invalid_values.add(key)

    if missing_values:
        raise Exception(f"Missing metadata entries identified: {missing_values}")
    if invalid_values:
        raise Exception(f"Invalid metadata identified: {invalid_values}")
