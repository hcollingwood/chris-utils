# chris-utils

The chris-utils Python package is intended for use during the conversion of Level 0 to Level 1 data and 
contains tools to:
- read in Level 0 data
- produce COG files
- produce Zarr files
- produce PNG thumbnails
- produce COG thumbnails
- produce EO-SIP files
- produce SAFE files

This package has a dependency of Python 3.11 due to the EOPF package which is used for generation of COG 
and Zarr files.

## Installing
Add this package to your requirements and run locally, or install via pip.


## Usage

### SAFE archive

```python
from chris_utils.safe.safe_maker import make_safe

output = 'my/output/folder'
inputs = "path/to/files/to/be/safe/archived,another/path"

make_safe(inputs=inputs, output=output)
```

### EO-SIP 

#### COGs and Zarrs
```python
from chris_utils.eo_sip.eo_sip_converter import convert_eo_sip

output = 'my/output/folder'
inputs = "path/to/files/to/be/converted.tif,another/path.zarr"

convert_eo_sip(inputs=inputs, output=output)
```

#### SAFE
Safe files require both the files to be archived and the metadata. Metadata can be extracted from headers in COGs or Zarrs 
```python
from chris_utils.eo_sip.eo_sip_converter import convert_eo_sip

output = 'my/output/folder'
inputs = "path/to/file/to/be/converted.tif"
extras = "path/to/safe/file.SAFE"

convert_eo_sip(inputs=inputs, output=output, extras=extras)
```

## Tests
Tests are written for [pytest](https://pytest.org/). To run tests, run `pytest tests` from the top level.