import os
import re
from datetime import datetime
from typing import Dict, List


def parse_chris_hdr_txt(txt_path: str, keep_spectral_table: bool = False) -> Dict[str, str]:
    """
    Parse a CHRIS ASCII header dump (e.g. *.hdr.txt) into a metadata dict.
    Supports:
      - Lines like "//Key<TAB>Value" or "//Key  Value"
      - Key lines "//Key" followed by a non-comment line as value
    If keep_spectral_table=True, the WLLOW… table is returned under
    meta['spectral_table'] as a list of dicts.
    """

    # check file existence & readability
    if not os.path.isfile(txt_path):
        raise FileNotFoundError(f"CHRIS metadata file not found: {txt_path}")
    if not os.access(txt_path, os.R_OK):
        raise PermissionError(f"Cannot read CHRIS metadata file: {txt_path}")

    meta = {}
    last_key = None

    columns: List[str] = []
    spectral_rows: List[Dict[str, str]] = []
    in_table = False

    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")

            # comment lines start with "//"
            if raw.startswith("//"):
                text = raw.lstrip("/").strip()

                # detect start of spectral table
                if text.upper().startswith("WLLOW"):
                    in_table = True
                    if keep_spectral_table:
                        columns = re.split(r"\s+", text)
                    continue

                # once we're in the table, collect rows until non-table
                if in_table and keep_spectral_table:
                    row_vals = re.split(r"\s+", text)
                    # only add if same length as header
                    if len(row_vals) == len(columns):
                        spectral_rows.append(dict(zip(columns, row_vals, strict=False)))
                    continue

                # if not keeping the table, skip it
                if in_table and not keep_spectral_table:
                    continue

                # skip pure headers / section titles
                if not text or text.upper().endswith("ATTRIBUTES"):
                    last_key = None
                    continue

                # inline key/value on same line?
                if "\t" in text or "  " in text:
                    parts = text.split("\t") if "\t" in text else re.split(r" {2,}", text)
                    key, val = parts[0].strip(), parts[-1].strip()
                    meta[key] = val
                    last_key = None
                else:
                    # might be a key waiting for the next line
                    last_key = text

            else:
                # non-comment line: if awaiting a key, grab it
                if last_key and raw.strip():
                    meta[last_key] = raw.strip()
                    last_key = None
                # or if in the table and keeping it, collect data
                elif in_table and keep_spectral_table and raw.strip():
                    row_vals = re.split(r"\s+", raw.strip())
                    if len(row_vals) == len(columns):
                        spectral_rows.append(dict(zip(columns, row_vals, strict=False)))

    # attach spectral table if we collected it
    if keep_spectral_table:
        meta["spectral_table"] = spectral_rows

    return meta


def build_eopf_root_attrs(chris_meta: dict, hdr_filename: str) -> dict:
    """
    Map CHRIS metadata dict and header filename into EOPF root .zattrs fields.
    Derives 'id' from the filename by stripping extensions (.hdr and .txt).
    """
    attrs = {}
    # derive id from filename
    stem = os.path.basename(hdr_filename)
    stem = re.sub(r"\.txt$", "", stem)
    stem = re.sub(r"\.hdr$", "", stem)
    attrs["id"] = stem
    attrs["product_type"] = "CHRIS-RCI"
    # datetime
    date = chris_meta.get("Image Date (yyyy-mm-dd)")
    centre = chris_meta.get("Calculated Image Centre Time")
    if date and centre:
        try:
            dt = datetime.strptime(f"{date} {centre}", "%Y-%m-%d %H:%M:%S")
            attrs["datetime"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            attrs["datetime"] = f"{date}T{centre}Z"
    # platform & instrument
    attrs["platform"] = "ESA PROBA"
    sensor = chris_meta.get("Sensor Type")
    if sensor:
        attrs["instrument"] = sensor
    # center coordinates
    lon = chris_meta.get("Longitude")
    lat = chris_meta.get("Lattitude")
    if lon and lat:
        try:
            attrs["center_lon"] = lon
            attrs["center_lat"] = lat
        except ValueError:
            attrs["center_point"] = [lon, lat]
    # copy all other fields prefixed
    for k, v in chris_meta.items():
        clean = re.sub(r"[^0-9a-zA-Z_]+", "_", k).lower()
        if clean in attrs:
            continue
        attrs[f"chris_{clean}"] = v
    return attrs
