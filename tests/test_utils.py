import tempfile

import pytest

from chris_utils.utils import check_metadata, get_list_of_files, get_version


def test_get_list_of_files(fs):
    top_level_path = "/home/top_level"
    cog_path = "/home/top_level/subdir/cog/cog.cog"
    zarr_path = "/home/top_level/subdir/zarr/zarr.zarr"
    safe_path = "/home/top_level/subdir/safe/safe.SAFE"
    unrelated_path = "/home/top_level/subdir/other/other.other"
    paths = [top_level_path, cog_path, zarr_path, safe_path, unrelated_path]

    for p in paths:
        fs.create_dir(p)
    fs.create_file(f"{top_level_path}/this/is/a/file.txt")

    list_of_files = get_list_of_files([top_level_path])
    assert len(list_of_files) == 3
    assert cog_path in list_of_files
    assert zarr_path in list_of_files
    assert safe_path in list_of_files


def test_get_version():
    root = "file_root"
    suffix = ".sfx"

    with tempfile.TemporaryDirectory() as tmpdir:
        version = get_version(root, suffix, tmpdir)
        assert version == "0001"

        with open(f"{tmpdir}/{root}_0001{suffix}", "w") as f:
            f.write("file contents")

        version = get_version(root, suffix, tmpdir)
        assert version == "0002"


@pytest.fixture()
def mock_metadata():
    return {
        "center_lat": 31.6,
        "center_lon": -110.54,
        "chris_calculated_image_centre_time": "18:18:16",
        "chris_chris_mode": "3",
        "chris_image_date_yyyy_mm_dd_": "2004-04-11",
        "chris_lattitude": "031.60",
        "chris_longitude": "-110.54",
        "datetime": "2004-04-11T18:18:16Z",
        "wavelength": [
            0.0,
            442.5,
            491.1,
            530.8,
            552.1,
            570.6,
            631.9,
            661.5,
            674.8,
            697.5,
            706.5,
            712.6,
            741.6,
            751.8,
            780.6,
            871.2,
            894.2,
            908.6,
            1016.8,
        ],
    }


@pytest.fixture
def regex_checks():
    return {
        "chris_lattitude": r"[-]?\d+\.\d+",
        "chris_longitude": r"[-]?\d+\.\d+",
        "chris_chris_mode": r"([1-5]|hrc)",
        "chris_image_date_yyyy_mm_dd_": r"[A-z0-9-\s]+",
        "chris_calculated_image_centre_time": r"[A-z0-9-:\s]+",
    }


@pytest.fixture
def list_checks():
    return {
        "wavelength": float,
    }


@pytest.fixture
def numeric_string_checks():
    return {"chris_lattitude": [-90, 90], "chris_longitude": [-180, 180]}


@pytest.fixture
def datetime_string_checks():
    return {
        "chris_image_date_yyyy_mm_dd_": "%Y-%m-%d",
        "chris_calculated_image_centre_time": "%H:%M:%S",
    }


def test_check_metadata__success(
    mock_metadata, regex_checks, list_checks, datetime_string_checks, numeric_string_checks
):

    check_metadata(
        metadata=mock_metadata,
        regex_checks=regex_checks,
        list_checks=list_checks,
        datetime_string_checks=datetime_string_checks,
        numeric_string_checks=numeric_string_checks,
    )


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("chris_lattitude"),
        pytest.param("chris_longitude"),
        pytest.param("chris_chris_mode"),
        pytest.param("chris_image_date_yyyy_mm_dd_"),
        pytest.param("chris_calculated_image_centre_time"),
    ],
)
def test_check_metadata__missing_data_fail(field, mock_metadata, regex_checks):

    del mock_metadata[field]
    with pytest.raises(Exception) as err:
        check_metadata(metadata=mock_metadata, regex_checks=regex_checks)

    assert "Missing metadata entries identified" in str(err.value)
    assert field in str(err.value)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("chris_image_date_yyyy_mm_dd_", "-2025-01-01"),
        pytest.param("chris_image_date_yyyy_mm_dd_", "2025-13-01"),
        pytest.param("chris_image_date_yyyy_mm_dd_", "2025-01-01 12:34:56"),
        pytest.param("chris_calculated_image_centre_time", "2025-01-01"),
        pytest.param("chris_calculated_image_centre_time", "12:34:65"),
        pytest.param("chris_calculated_image_centre_time", "2025-12-01 12:34:56"),
    ],
)
def test_check_metadata__datetime_fail(field, value, mock_metadata, datetime_string_checks):

    mock_metadata[field] = value
    with pytest.raises(Exception) as err:
        check_metadata(metadata=mock_metadata, datetime_string_checks=datetime_string_checks)

    assert "Invalid metadata identified" in str(err.value)
    assert field in str(err.value)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("chris_image_date_yyyy_mm_dd_", "2025-01-01"),
        pytest.param("chris_calculated_image_centre_time", "12:34:56"),
    ],
)
def test_check_metadata__datetime_pass(field, value, mock_metadata, datetime_string_checks):

    check_metadata(metadata=mock_metadata, datetime_string_checks=datetime_string_checks)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("wavelength", [1, "b", 3, "d", 5]),
    ],
)
def test_check_metadata__list_fail(field, value, mock_metadata, list_checks):

    mock_metadata[field] = value
    with pytest.raises(Exception) as err:
        check_metadata(metadata=mock_metadata, list_checks=list_checks)

    assert "Invalid metadata identified" in str(err.value)
    assert field in str(err.value)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("wavelength", [1, 2, 3, 4, 5]),
    ],
)
def test_check_metadata__list_pass(field, value, mock_metadata, list_checks):
    check_metadata(metadata=mock_metadata, list_checks=list_checks)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("chris_lattitude", "2025-01-01"),
        pytest.param("chris_lattitude", "123.45"),
        pytest.param("chris_lattitude", "0123.45"),
        pytest.param("chris_lattitude", "-123.45"),
        pytest.param("chris_lattitude", 12.34),
        pytest.param("chris_longitude", "2025-01-01"),
        pytest.param("chris_longitude", "01234.56"),
        pytest.param("chris_longitude", "1234.56"),
        pytest.param("chris_longitude", "-1234.56"),
        pytest.param("chris_longitude", 123.45),
    ],
)
def test_check_metadata__numeric_fail(field, value, mock_metadata, numeric_string_checks):

    mock_metadata[field] = value
    with pytest.raises(Exception) as err:
        check_metadata(metadata=mock_metadata, numeric_string_checks=numeric_string_checks)

    assert "Invalid metadata identified" in str(err.value)
    assert field in str(err.value)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("chris_chris_mode", "1"),
        pytest.param("chris_chris_mode", "2"),
        pytest.param("chris_chris_mode", "3"),
        pytest.param("chris_chris_mode", "4"),
        pytest.param("chris_chris_mode", "5"),
        pytest.param("chris_chris_mode", "hrc"),
    ],
)
def test_check_metadata__regex_pass(field, value, mock_metadata, regex_checks):
    check_metadata(metadata=mock_metadata, regex_checks=regex_checks)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("chris_chris_mode", "6"),
        pytest.param("chris_chris_mode", "10"),
        pytest.param("chris_chris_mode", "abc"),
    ],
)
def test_check_metadata__regex_fail(field, value, mock_metadata, regex_checks):

    mock_metadata[field] = value
    with pytest.raises(Exception) as err:
        check_metadata(metadata=mock_metadata, regex_checks=regex_checks)

    assert "Invalid metadata identified" in str(err.value)
    assert field in str(err.value)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("chris_lattitude", "012.34"),
        pytest.param("chris_lattitude", "-012.34"),
        pytest.param("chris_longitude", "123.45"),
        pytest.param("chris_longitude", "-123.45"),
    ],
)
def test_check_metadata__numeric_pass(field, value, mock_metadata, numeric_string_checks):

    mock_metadata[field] = value
    check_metadata(metadata=mock_metadata, numeric_string_checks=numeric_string_checks)
