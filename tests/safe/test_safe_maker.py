import pytest

from chris_utils.safe.safe_maker import calculate_crc_checksum


@pytest.mark.parametrize(
    "raw_string,expected_value",
    [
        pytest.param("test string", "61CA"),
        pytest.param("ABC123", "1659"),
    ],
)
def test_calculate_checksum(raw_string, expected_value):
    actual_value = calculate_crc_checksum(raw_string)

    assert actual_value == expected_value
