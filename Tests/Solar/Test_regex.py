"""Test the regex responsible for parsing metric attributes."""

from Charts.Solar.Helpers import (
    extract_weather_station,
    extract_inverter,
)


def test_extract_weather_station():
    column = "BWS-BLK02-PCS006-WS2-GHI_eucl"

    expected_output = "WS2"
    actual_output = extract_weather_station(column)
    assert expected_output == actual_output

def test_extract_inverter_letters():
    column = "BWS BLK02 PCS002 INVA"

    expected_output = "INVA"
    actual_output = extract_inverter(column)
    assert expected_output == actual_output

def test_extract_inverter_numeric():
    column = "ADB BLK01 PCS005 INV09"

    expected_output = "INV09"
    actual_output = extract_inverter(column)
    assert expected_output == actual_output
