import tempfile
from chris_utils.safe.manifest_xml_generator import calculate_md5_checksum


def test_calculate_md5_checksum():

    expected_checksum = "d41d8cd98f00b204e9800998ecf8427e"

    with tempfile.NamedTemporaryFile() as tf:
        tf.write(b"Sample text goes here")

        actual_checksum = calculate_md5_checksum(tf.name)

    assert actual_checksum == expected_checksum
