"""Constants for the Front End."""
import os

from dash import html

APP_TITLE = "iSight"
if os.environ["ENV_TITLE"] != "":
    APP_TITLE += f" ({os.environ['ENV_TITLE']})"
DESCRIPTION_CODE_DELIM = " | "
DATE_PRESET_SELECTION_VALUE_DELIMITER = "|"
METRIC_UNITS = {
    "Lost Revenue": "$",
    "Lost Energy": "MWh",
    "Downtime": "Hours",
    "Count": "Occurences",
}

FAULT_PULSE_PARETO_CHART_HEIGHT = 600
DEFAULT_CHART_HEIGHT = (
    500  # Changed from 450 to 500, this is the num of Pixels in a chart - FBB 12/23
)
COMPONENT_TEMPERATURE_SUBCHART_HEIGHT = 350
COMPONENT_TEMPERATURE_HEATMAP_DEFAULT_SORTING = "by-turbine"  # other option is 'by-component'
HIDDEN_STYLE = {"visibility": "hidden", "height": "0"}
VISIBLE_STYLE = {"visibility": "visible", "height": "auto"}
PARETO_COLORS = {
    "normal": "#ABABAB",
    "highlight": "#FCFFA3",
}
BLUE_COLOR = "#007AB8"


# Performance and Reliability Constants

PERFORMANCE_METRICS = [
    "-LOST-REVENUE",
    "-LOST-ENERGY",
    "-SEVERITY",
]
PERFORMANCE_METRICS_LABEL_LOOKUP = {
    "-LOST-REVENUE": "Lost Revenue",
    "-LOST-ENERGY": "Lost Energy",
    "-SEVERITY": "Relative Deviation",
}
POWER_PERFORMANCE_TREEMAP_OPTIONS = [
    {
        "label": html.Span(
            id=val,
            children=PERFORMANCE_METRICS_LABEL_LOOKUP[val],
        ),
        "value": val,
    }
    for val in PERFORMANCE_METRICS
]


# Fault Page

PEBBLE_CHART_METRICS = [
    "Lost Revenue",
    "Lost Energy",
    "Downtime",
]
TURBINE_FAULT_CODE_COUNT = 10
NULL_FAULT_DESCRIPTION = "DESCRIPTION MISSING"
TURBINE_FAULT_DELIM = " - "
ALL_FAULT_CHART_METRICS = [
    "Lost Revenue",
    "Lost Energy",
    "Count",
    "Downtime",
]
FAULT_METRIC_LOOKUP = {
    "Downtime": "Downtime",
    "Lost Revenue": "LostRevenue",
    "Lost Energy": "LostEnergy",
    "Count": "FaultCount",
}

FAULT_METRIC_COLUMN_LOOKUP = {
    "Downtime": "Downtime",
    "LostRevenue": "Lost Revenue",
    "LostEnergy": "Lost Energy",
    "FaultCount": "Count",
}
REV_FAULT_METRIC_COLUMN_LOOKUP = {
    val: key for key, val in FAULT_METRIC_COLUMN_LOOKUP.items()
}
