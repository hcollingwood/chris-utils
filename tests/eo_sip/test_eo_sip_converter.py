import copy
import os
import tempfile
import zipfile

import pytest

from chris_utils.eo_sip.eo_sip_converter import (
    do_metadata_check,
    format_latitude,
    format_longitude, identify_centre_image, Data, zip_directory,
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
    do_metadata_check(metadata=mock_metadata)


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


def test_identify_centre_image__all_present(mock_metadata):
    all_data = []
    for i in range(1, 6):
        temp_metadata = copy.deepcopy(mock_metadata)
        temp_metadata['chris_image_no_x_of_y'] = f'{i} of 5'
        all_data.append(Data(raw_metadata=temp_metadata, file_data=None, raw_data=None, image=None))

    centre_metadata = identify_centre_image(all_data)

    assert centre_metadata.raw_metadata['chris_image_no_x_of_y'] == '1 of 5'


def test_identify_centre_image__missing_one(mock_metadata):
    all_data = []
    for i in range(2, 6):
        temp_metadata = copy.deepcopy(mock_metadata)
        temp_metadata['chris_image_no_x_of_y'] = f'{i} of 5'
        all_data.append(Data(raw_metadata=temp_metadata, file_data=None, raw_data=None, image=None))

    centre_metadata = identify_centre_image(all_data)

    assert centre_metadata.raw_metadata['chris_image_no_x_of_y'] == '2 of 5'


def test_identify_centre_image__missing_two(mock_metadata):
    all_data = []
    for i in range(3, 6):
        temp_metadata = copy.deepcopy(mock_metadata)
        temp_metadata['chris_image_no_x_of_y'] = f'{i} of 5'
        all_data.append(Data(raw_metadata=temp_metadata, file_data=None, raw_data=None, image=None))

    centre_metadata = identify_centre_image(all_data)

    assert centre_metadata.raw_metadata['chris_image_no_x_of_y'] == '3 of 5'


def test_identify_centre_image__duplicates(mock_metadata):
    all_data = []
    for i in range(2, 6):
        temp_metadata = copy.deepcopy(mock_metadata)
        temp_metadata['chris_image_no_x_of_y'] = '1 of 5'
        all_data.append(Data(raw_metadata=temp_metadata, file_data=None, raw_data=None, image=None))

    centre_metadata = identify_centre_image(all_data)

    assert centre_metadata.raw_metadata['chris_image_no_x_of_y'] == '1 of 5'


def test_zip_directory():
    with tempfile.TemporaryDirectory() as tempdir1, tempfile.TemporaryDirectory() as tempdir2:
        if not os.path.exists(tempdir1):
            os.makedirs(tempdir1)
        if not os.path.exists(tempdir2):
            os.makedirs(tempdir2)

        for i in range(5):
            output_dir = f'{tempdir1}/outputs{i}'
            os.makedirs(output_dir)
            with open(f'{output_dir}/file{i}.txt', 'w') as f:
                f.write(str(i) * 100)

        assert len(os.listdir(tempdir1)) == 5

        zip_name = 'folder contents'
        folder_dir = tempdir1
        with zipfile.ZipFile(f'{tempdir2}/output.zip', 'w') as zip_file:
            zip_directory(folder_dir, zip_name, zip_file)

        assert len(os.listdir(tempdir2)) == 1
        assert 'output.zip' in os.listdir(tempdir2)

        with zipfile.ZipFile(f'{tempdir2}/output.zip', 'r') as zip_file_outer:
            zip_file_outer.extractall(tempdir2)

        assert len(os.listdir(f"{tempdir2}/{zip_name}")) == 5
        for item in os.listdir(f"{tempdir2}/{zip_name}"):
            assert os.path.isdir(f"{tempdir2}/{zip_name}/{item}")
