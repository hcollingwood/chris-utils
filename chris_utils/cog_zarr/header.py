def parse_envi_header(hdr_path: str) -> dict:
    """
    Parse an ENVI-style ASCII header (.hdr) file into a Python dict.
    """
    hdr = {}
    with open(hdr_path, "r") as f:
        for line in f:
            if "=" not in line:
                continue
            key, val = map(str.strip, line.split("=", 1))
            key_l = key.lower()

            # strip braces
            if val.startswith("{") and val.endswith("}"):
                val = val[1:-1]

            # list-valued (e.g. wavelength)
            if "," in val and ("{" in line or key_l == "wavelength"):
                items = [v.strip() for v in val.split(",")]
                try:
                    items = [float(v) for v in items]
                except ValueError:
                    pass
                hdr[key_l] = items
            else:
                # numeric or string
                try:
                    hdr[key_l] = float(val)
                    hdr[key_l] = int(hdr[key_l]) if hdr[key_l].is_integer() else hdr[key_l]

                except ValueError:
                    hdr[key_l] = val
    return hdr
