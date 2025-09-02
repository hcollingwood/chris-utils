import logging
import os

def get_list_of_files(inputs):
    files = []
    error_message = "%s not recognised. Ensure that path is valid"
    for i in inputs:
        if os.path.isfile(i):
            files.append(i)
        elif os.path.isdir(i):
            if i.endswith('.zarr'):
                files.append(i)
            elif i.endswith('.SAFE'):
                files.append(i)
            else:
                for file in os.listdir(i):
                    files.append(f"{i}/{file}")

        else:
            logging.error(error_message, i)

    return files