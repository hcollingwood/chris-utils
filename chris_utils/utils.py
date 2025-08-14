import os

def get_list_of_files(inputs):
    files = []
    for i in inputs:
        if os.path.isfile(i):
            files.append(i)
        if os.path.isdir(i):
            if i.endswith('.zarr'):
                files.append(i)
            elif i.endswith('.SAFE'):
                files.append(i)
            else:
                for file in os.listdir(i):
                    files.append(f"{i}/{file}")

    return files