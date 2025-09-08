import logging
import os



def get_list_of_files(inputs):
    files = []

    error_message = "%s not recognised. Ensure that path is valid"

    def process_input(i):
        # if os.path.isfile(i) and i.endswith('.cog'):
        #     files.append(i)
        #     print(i, "file")
        if os.path.isdir(i):
            if i.lower().endswith('.zarr') or i.lower().endswith('.cog'):
                files.append(i)
            elif i.endswith('.SAFE'):
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