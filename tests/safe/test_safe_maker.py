import os
import tempfile

import pytest

from chris_utils.safe.safe_maker import (
    calculate_crc_checksum,
    generate_file_name,
    write_manifest,
    make_safe,
)


@pytest.fixture
def mock_metadata():
    return {"ImageDate(yyyymmdd)": "19700101", "CalculatedImageCentreTime": "12:34:56"}


@pytest.mark.parametrize(
    "raw_string,expected_value",
    [
        pytest.param("test string", "61CA"),
        pytest.param("ABC123", "1659"),
    ],
)
def test_calculate_crc_checksum(raw_string, expected_value):
    actual_value = calculate_crc_checksum(raw_string)

    assert actual_value == expected_value


def test_write_manifest():
    test_string = "test text"

    with tempfile.TemporaryDirectory() as tempdir:
        write_manifest(test_string, tempdir)

        with open(tempdir + "/MANIFEST.XML") as f:
            lines = f.readlines()
            assert lines == [test_string]


def test_generate_file_name__success(mock_metadata):
    suffix = ".test"
    output_path = "/path/to/file"
    file_name = generate_file_name(mock_metadata, suffix, output_path)

    assert file_name == "CHRIS_19700101T123456_0001.test"


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("ImageDate(yyyymmdd)"),
        pytest.param("CalculatedImageCentreTime"),
    ],
)
def test_generate_file_name__failure_missing_data(mock_metadata, key):
    suffix = ".test"
    output_path = "/path/to/file"
    bad_metadata = mock_metadata
    del bad_metadata[key]

    with pytest.raises(Exception) as err:
        generate_file_name(bad_metadata, suffix, output_path)

    assert "Required metadata not available" in str(err)


def test_generate_file_name__failure_wrong_type(mock_metadata):
    suffix = ".test"
    output_path = "/path/to/file"
    bad_metadata = "this is a string and not a dictionary"

    with pytest.raises(Exception) as err:
        generate_file_name(bad_metadata, suffix, output_path)

    assert "Metadata not recognised" in str(err)


def test_make_safe():
    input_file_name = "myfile.txt"  # only important part here is the .txt extension
    expected_file_name = "CHRIS_20040411T181816_0001_RPI-BAS_64F3.SAFE"
    with tempfile.TemporaryDirectory() as tempdir:
        with open(tempdir + "/" + input_file_name, "w") as f:
            f.write(
                "//Image Date (yyyy-mm-dd)\n2004-04-11\n//Calculated Image Centre Time\n18:18:16"
            )

        make_safe(inputs=tempdir, output=tempdir, package_type="RPI-BAS")

        safe_path = f"{tempdir}/{expected_file_name}"
        all_files = os.listdir(tempdir)
        assert len(all_files) == 2  # original file and SAFE package
        assert expected_file_name in all_files
        assert os.path.isdir(safe_path)

        metadata_path = f"{safe_path}/metadata"
        measurement_path = f"{safe_path}/measurement"
        assert os.path.isdir(metadata_path)
        assert os.path.isdir(measurement_path)
        assert os.path.isfile(f"{safe_path}/MANIFEST.XML")

        metadata_contents = os.listdir(metadata_path)
        assert "txt.xsd" in metadata_contents

        measurement_contents = os.listdir(measurement_path)

        assert "MEASUREMENT-txt.dat" in measurement_contents
        assert (
            open(f"{tempdir}/{input_file_name}").read()
            == open(f"{measurement_path}/MEASUREMENT-txt.dat").read()
        )
