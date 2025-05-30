"""Helper Functions for the Solar Charting Functions."""

import re

from Utils.ISightConstants import PI_TAG_REGEX_PATTERN_LOOKUP


def extract_plant(column):
    """Get the plant substring from a column."""
    return column[:3]


def extract_block(column):
    """Get the block substring from a column."""
    pattern = PI_TAG_REGEX_PATTERN_LOOKUP["block"]
    m = re.search(pattern=pattern, string=column)
    if m:
        return column[m.start() : m.end()]
    return m


def extract_power_conversion_station(column):
    """Get the power conversion station substring from a column."""
    pattern = PI_TAG_REGEX_PATTERN_LOOKUP["power_conversion_station"]
    m = re.search(pattern, column)
    if m:
        return m.group(1)
    return m


def extract_weather_station(column):
    """Get the weather station substring from a column."""
    pattern = PI_TAG_REGEX_PATTERN_LOOKUP["weather_station"]
    m = re.search(pattern=pattern, string=column)
    if m:
        return column[m.start() : m.end()]
    return m


def extract_measurement(column):
    """Get the measurement substring from a column."""
    pattern = PI_TAG_REGEX_PATTERN_LOOKUP["measurement"]
    m = re.search(pattern=pattern, string=column)
    if m:
        return column[m.start() : m.end()]
    return m


def extract_metric(column):
    """Get the metric substring from a column."""
    return column[column.find("_") + 1 :]


def extract_base(column):
    """Return the part of the column name besides the metric."""
    return column.split("_", 1)[0]


def extract_inverter(column):
    """Get the inverter substring from a column."""
    pattern = PI_TAG_REGEX_PATTERN_LOOKUP["inverter"]
    m = re.search(pattern=pattern, string=column)
    if m:
        return column[m.start() : m.end()]
    return m

def decide_plants_to_show(conn, self_perform_checkbox, plant_filter):
    """Decide the Plants to show from global selections.

    This helper function is used to decide what plants
    to show across various charts.
    """
    if self_perform_checkbox:
        plant_arr = conn.get_self_perform_plants()
    elif plant_filter == "All":
        plant_arr = None
    else:
        plant_arr = [plant_filter]
    return plant_arr

def gen_plant_subtitle(plant_arr):
    """Create a text blurb for display in chart titles."""
    if plant_arr is None:
        substring_plant = "All Plants"
    elif len(plant_arr) == 1:
        substring_plant = plant_arr[0]
    else:
        substring_plant = f"{len(plant_arr)} Self-Performing Plants"
    return substring_plant
