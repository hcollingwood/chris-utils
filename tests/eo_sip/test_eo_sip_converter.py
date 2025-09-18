import pytest

from chris_utils.eo_sip.eo_sip_converter import (
    check_metadata,
    format_latitude,
    format_longitude,
)


@pytest.fixture()
def mock_metadata():
    return {
        "bands": 19,
        "byte order": 0,
        "center_lat": 31.6,
        "center_lon": -110.54,
        "chris_altitude_in_m": "01500",
        "chris_calculated_image_centre_time": "18:18:16",
        "chris_calibration_data_units": "microWatts/nm/m^2/str",
        "chris_chris_mode": "3",
        "chris_chris_temperature": "004.79",
        "chris_dark_file_creation_time": "2002-13-19 15:38",
        "chris_fly_by_time": "18:18",
        "chris_fly_by_zenith_angle": "0",
        "chris_gain_setting": "Gain Value",
        "chris_image_date_yyyy_mm_dd_": "2004-04-11",
        "chris_image_no_x_of_y": "1 of 5",
        "chris_image_tag_number": "3FB1",
        "chris_image_target_code": "AU",
        "chris_lattitude": "031.60",
        "chris_longitude": "-110.54",
        "chris_mask_key_information": "0 = useful pixels;"
        "1 = Ch2 reset pixels;"
        "2 = Saturated data pixels",
        "chris_minimum_zenith_angle": "025",
        "chris_no_of_bands_followed_by_band_position_of_smear": "018",
        "chris_no_of_ground_lines": "0748",
        "chris_no_of_samples": "766",
        "chris_observation_azimuth_angle": "136.64",
        "chris_observation_zenith_angle": "25.92",
        "chris_platform_altitude_in_km": "0547",
        "chris_response_file_creation_time": "2004-13-18 10:56",
        "chris_sensor_type": "CHRIS",
        "chris_solar_zenith_angle": "028.00",
        "chris_statement_of_data_rights": "Sira Technology Ltd is the owner of all data "
        "directly resulting from in-flight operation of the "
        "CHRIS instrument flown on-board the ESA PROBA "
        "spacecraft.  All publications on the CHRIS "
        "instrument or data obtained from the CHRIS "
        "development and/or operation shall make explicit "
        "reference to Sira Technology Ltd the CHRIS instrument "
        "and the ESA PROBA mission.",
        "chris_target_name": "Audobon",
        "data type": 3,
        "datetime": "2004-04-11T18:18:16Z",
        "description": "Audobon",
        "file type": "ENVI Standard",
        "header offset": 0,
        "id": "CHRIS_AU_040411_3FB1_41",
        "instrument": "CHRIS",
        "interleave": "bsq",
        "lines": 748,
        "other_metadata": {"eopf_category": "eoproduct"},
        "platform": "ESA PROBA",
        "product_type": "CHRIS-RCI",
        "samples": 766,
        "sensor type": "CHRIS",
        "stac_discovery": {
            "properties": {
                "instrument": "CHRIS",
                "platform": "ESA PROBA",
                "processing:version": "",
                "product:type": "CHRIS-RCI",
                "start_datetime": "2004-04-11T18:18:16Z",
            }
        },
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


def test_check_metadata__success(mock_metadata):

    check_metadata(mock_metadata)


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
def test_check_metadata__missing_data_fail(field, mock_metadata):

    del mock_metadata[field]
    with pytest.raises(Exception) as err:
        check_metadata(mock_metadata)

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
def test_check_metadata__datetime_fail(field, value, mock_metadata):

    mock_metadata[field] = value
    with pytest.raises(Exception) as err:
        check_metadata(mock_metadata)

    assert "Invalid metadata identified" in str(err.value)
    assert field in str(err.value)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("chris_image_date_yyyy_mm_dd_", "2025-01-01"),
        pytest.param("chris_calculated_image_centre_time", "12:34:56"),
    ],
)
def test_check_metadata__datetime_pass(field, value, mock_metadata):

    check_metadata(mock_metadata)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("wavelength", [1, "b", 3, "d", 5]),
    ],
)
def test_check_metadata__list_fail(field, value, mock_metadata):

    mock_metadata[field] = value
    with pytest.raises(Exception) as err:
        check_metadata(mock_metadata)

    assert "Invalid metadata identified" in str(err.value)
    assert field in str(err.value)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("wavelength", [1, 2, 3, 4, 5]),
    ],
)
def test_check_metadata__list_pass(field, value, mock_metadata):

    check_metadata(mock_metadata)


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
def test_check_metadata__numeric_fail(field, value, mock_metadata):

    mock_metadata[field] = value
    with pytest.raises(Exception) as err:
        check_metadata(mock_metadata)

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
def test_check_metadata__regex_pass(field, value, mock_metadata):

    check_metadata(mock_metadata)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("chris_chris_mode", "6"),
        pytest.param("chris_chris_mode", "10"),
        pytest.param("chris_chris_mode", "abc"),
    ],
)
def test_check_metadata__regex_fail(field, value, mock_metadata):

    mock_metadata[field] = value
    with pytest.raises(Exception) as err:
        check_metadata(mock_metadata)

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
def test_check_metadata__numeric_pass(field, value, mock_metadata):

    mock_metadata[field] = value
    check_metadata(mock_metadata)


@pytest.mark.parametrize(
    "raw,expected_format",
    [
        pytest.param("012.34", "N12-340"),
        pytest.param("-012.34", "S12-340"),
        pytest.param("-012.034", "S12-034"),
    ],
)
def test_format_latitude__pass(raw, expected_format):

    formatted = format_latitude(raw)
    assert formatted == expected_format


@pytest.mark.parametrize(
    "raw,expected_format",
    [
        pytest.param("012.34", "E012-340"),
        pytest.param("123.456", "E123-456"),
        pytest.param("-012.34", "W012-340"),
        pytest.param("-012.034", "W012-034"),
    ],
)
def test_format_longitude__pass(raw, expected_format):

    formatted = format_longitude(raw)
    assert formatted == expected_format
