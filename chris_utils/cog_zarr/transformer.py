import logging

from .eopf_utils import write_eopf_cog, write_eopf_zarr
from .reader import RCIReader


def transform(
    rci,
    hdr,
    hdr_txt,
    bands=None,
    scale=None,
    dtype=None,
    zarr=None,
    cog=None,
    eopf_zarr=None,
    eopf_cog=None,
    gps_file=None,
    centre_times_file=None,
):
    """Convert CHRIS .rci to COG, plain Zarr, and/or EOPF-compliant Zarr."""
    # parse band list
    band_list = [int(b) for b in bands.split(",")] if bands else None

    # read via our RCIReader
    reader = RCIReader(
        rci,
        hdr,
        scale_factor=scale,
        out_bands=band_list,
        out_dtype=dtype,
        hdr_txt_path=hdr_txt,
        gps_file=gps_file,
        centre_times_file=centre_times_file,
    )
    da = reader.read()

    # 1) plain Zarr
    if zarr:
        reader.to_zarr(zarr)
        logging.info(f"Saved Zarr to {zarr}")

    # 2) COG
    if cog:
        reader.to_cog(cog)
        logging.info(f"Saved COG to {cog}")

    # 3) EOPF-compliant Zarr
    if eopf_zarr:
        write_eopf_zarr(
            da,
            reader.header,
            hdr_txt,
            eopf_zarr,
        )
        logging.info(f"Saved EOPF Zarr to {eopf_zarr}")
    # 4) EOPF-compliant Cog
    if eopf_cog:
        write_eopf_cog(
            da,
            reader.header,
            hdr_txt,
            eopf_cog,
        )
        logging.info(f"Saved EOPF COG to {eopf_cog}")
