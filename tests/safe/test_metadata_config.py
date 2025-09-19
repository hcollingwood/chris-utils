from chris_utils.safe.metadata_config import dat_schema, txt_schema, hdr_schema, set_schema


# These tests aren't very thorough and don't test the contents of the schema but they will fail if the schema is invalid
def test_dat_schema():
    schema = dat_schema()
    assert schema.element.name == "pixel"
    assert schema.element.type == "pixelType"


def test_txt_schema():
    schema = txt_schema()
    assert schema.element.name == "txt"
    assert schema.element.type == "txtType"


def test_hdr_schema():
    schema = hdr_schema()
    assert schema.element.name == "hdr"
    assert schema.element.type == "hdrType"


def test_set_schema():
    schema = set_schema()
    assert schema.element.name == "set"
    assert schema.element.type == "setType"
