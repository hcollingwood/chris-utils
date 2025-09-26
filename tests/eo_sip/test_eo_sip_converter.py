import pytest

from chris_utils.eo_sip.eo_sip_converter import (
    format_latitude,
    format_longitude, do_metadata_check,
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



def test_do_metadata_check__success(mock_metadata):
    do_metadata_check(metadata = mock_metadata)


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
