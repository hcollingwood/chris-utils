# chris-utils


## Installing
Add this package to your requirements and run locally

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