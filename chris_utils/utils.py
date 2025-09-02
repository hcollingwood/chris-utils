import logging
import os



def get_list_of_files(inputs):
    files = []

    def process_input(i):
        if os.path.isfile(i):
            files.append(i)
        elif os.path.isdir(i):
            if i.endswith('.zarr'):
                files.append(i)
            elif i.endswith('.SAFE'):
                files.append(i)
            else:
                for file in os.listdir(i):
                    item_path = os.path.join(i, file)
                    files.append(item_path)


    error_message = "%s not recognised. Ensure that path is valid"
    for i in inputs:
        process_input(i)

        if i not in files:
            logging.error(error_message, i)

    return files