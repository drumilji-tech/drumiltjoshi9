"""Constants for iSight."""

from dash import html


# Weather Station Health

# plant is excluded from the regex lookup since trival
PI_TAG_REGEX_PATTERN_LOOKUP = {
    "block": "(BLK\d*)",
    "power_conversion_station": "PCS([A-Za-z0-9]+)",
    "weather_station": "(WS\d+)",
    "measurement": "(BOM|POA|GHI)",
    "inverter": "(INV\w*)",
}

INIT_TORNADO_POINTS = 25
TORNADO_CHART_PLOTLY_CONFIG = {
    'displayModeBar': True,
    'doubleClick': False,
    'showAxisDragHandles': True,
    'modeBarButtonsToRemove': [
        'download',
        'zoom',
        'pan',
        'zoom2d',
        'pan2d',
        'select2d',
        'lasso2d',
        'zoomIn2d',
        'zoomOut2d',
        'autoScale2d',
        'resetViews',
        'resetScale2d',
    ]
}

MEASUREMENT_FULLNAME_LOOKUP = {
    "GHI": "Global Horizontal Irradiance",
    "POA": "Plane of Array Irradiance",
    "BOM": "Back of Module Temperature",
}
MEASUREMENT_UNITS_LOOKUP = {
    "GHI": "W/m²",
    "POA": "W/m²",
    "BOM": "°C",
}

DATABASE_METRIC_TRANSLATOR = {
    "euclidean": "eucl",
    "manhattan": "manh",
    "cosine": "cosine",
    "jensen-shanon": "js",
    "pct diff": "pct_diff",
}
REVERSE_DATABASE_METRIC_TRANSLATOR = {
    value: key for key, value in DATABASE_METRIC_TRANSLATOR.items()
}
if "" in REVERSE_DATABASE_METRIC_TRANSLATOR:
    del REVERSE_DATABASE_METRIC_TRANSLATOR[""]

METRICS_RADIOITEMS_OPTIONS = []
for key in DATABASE_METRIC_TRANSLATOR:
    option = {
        "label": html.Span(
            id=key,
            children=key.title(),
        ),
        "value": key,
        "disabled": False
    }
    if DATABASE_METRIC_TRANSLATOR[key] == "":
        option["disabled"] = True
    METRICS_RADIOITEMS_OPTIONS.append(option)


EUCLIDEAN_MARKDOWN_TEXT = """
The **Euclidean** metric measures the *square of the* difference between the actual measurement and SolarAnywhere reference data. This metric is sensitive to large regular deviations, meaning it emphasizes outliers.

Euclidean (MSE) and Manhattan (MAE) often diverge when these differences are characterized by more extreme deviations.

---

## Mathematical Explanation

$$
d(\\mathbf{p}, \\mathbf{q}) = \\sqrt{\\sum_{i=1}^{n} (p_i - q_i)^2}
$$

Where:
- $d(\mathbf{p}, \mathbf{q})$ is the Euclidean distance between points $\mathbf{p}$ and $\mathbf{q}$,
- $p_i$ and $q_i$ are the coordinates of points $\mathbf{p}$ and $\mathbf{q}$ in the $i$-th dimension.

Because of the squaring, this metric accumulates exponentially and thus disproportionately emphasizes larger pairwise differences.
"""

MANHATTAN_MARKDOWN_TEXT = """
The **Manhattan** metric captures the _absolute difference_ between the actual measurement and the SolarAnywhere reference data. This metric is sensitive to persistent deviations, meaning it deemphasizes outliers.

Euclidean (MSE) and Manhattan (MAE) often diverge when these differences are characterized by more extreme deviations. In particular, Manhattan distance penalizes small but frequent differences more heavily than Euclidean distance and is therefore useful for isolating issues characterized by smaller frequent *blips*.

---

## Mathematical Explanation

$$
d(\\mathbf{p}, \\mathbf{q}) = \\sum_{i=1}^{n} |p_i - q_i|
$$

Where:
- $d(\mathbf{p}, \mathbf{q})$ is the Manhattan distance between points $\mathbf{p}$ and $\mathbf{q}$,
- $p_i$ and $q_i$ are the coordinates of points $\mathbf{p}$ and $\mathbf{q}$ in the $i$-th dimension.

This metric accumulates linearly, meaning it gives equal weight to both large and small differences.
"""

COSINE_MARKDOWN_TEXT = """
The **Cosine** metric measures the similarity in the shape of data between the actual measurement and the SolarAnywhere reference data, regardless of magnitude and bias.

Jensen-Shanon measures the similarity between two distributions, whereas Cosine measures similarity by comparing patterns between values, regardless of how large or small the values are.

By analogy, it's like comparing two music notes. If two musical notes have a different tone, then they are dissimilar in shape (Cosine metric < 1). But if the two musical notes have the same tone but only differ in loudness, then they have similar shape (Cosine metric = 1).

---

## Mathematical Explanation

$$
d(\\mathbf{p}, \\mathbf{q}) = 1 - \\frac{\\sum_{i=1}^{n} p_i q_i}{\\sqrt{\\sum_{i=1}^{n} p_i^2} \\cdot \\sqrt{\\sum_{i=1}^{n} q_i^2}}
$$

Where:

- $d(\mathbf{p}, \mathbf{q})$ is the Cosine distance between points $\mathbf{p}$ and $\mathbf{q}$,
- $p_i$ and $q_i$ are the coordinates of points $\mathbf{p}$ and $\mathbf{q}$ in the $i$-th dimension.

The Cosine distance is a number that ranges between 0 and 1, where:
- 1 means the two time series are completely dissimilar and
- 0 means they are exactly the same.

It is not a pairwise, lock-step metric like Manhattan and Euclidean, but instead evaluates the direction of the vector defined by all 144 points in each day's 10 minute data.

Phase and Frequency have a heavy impact on Cosine distance, but distance between points has no effect as long as the shape is the same.
This allows cases to be isolated when there might be a phase shift or frequency difference in sensor measurements.

"""

JENSEN_SHANON_MARKDOWN_TEXT = """
The **Jensen-Shannon** metric measures how similar one probability distribution is to another. We use it to determine the similarity between our measured data and SolarAnywhere data.

---

Technically, it's a number ranging from 0 and 1, where:
- 0 indicates no difference between the distributions.
- 1 indicates the maximum possible difference between the distributions.

Jensen-Shanon measures the similarity between two distributions, whereas Cosine measures similarity by comparing patterns between values, regardless of how large or small the values are.
Jensen-Shanon distance is not concerned with when values occur in time, but rather how often they occur in each signal. Jensen-Shannon highlights rare but extreme outliers more than Euclidean, Manhattan, or Cosine.
Jensen-Shannon also detects differences in variance even if the pair-wise differences might be relatively small, a situation that Euclidean and Manhattan might overlook.

"""

PERCENT_DIFFERENCE_MARKDOWN_TEXT = """
The **Percent Difference** metric is the direct percentage difference between the measurement data and SolarAnywhere reference data.

In the tornado charts, each data point is color-coded to represent the absolute percent difference from SolarAnywhere.

- POA and GHI Tornado Charts use the sum (integral) of days in the selected period.
- The BOM Chart uses the average of days in the selected period (averaging is done in Kelvin units).

(Note that the actual signed percentage can be found by hovering over a specific data point.)

"""

SOLAR_TOOLTIP_TEXT_LOOKUP = {
    "euclidean": EUCLIDEAN_MARKDOWN_TEXT,
    "manhattan": MANHATTAN_MARKDOWN_TEXT,
    "cosine": COSINE_MARKDOWN_TEXT,
    "jensen-shanon": JENSEN_SHANON_MARKDOWN_TEXT,
    "pct diff": PERCENT_DIFFERENCE_MARKDOWN_TEXT,
}

SOLAR_TOOLTIP_GRAPHICS_LOOKUP = {
    "euclidean": "/assets/images/euclidean.png",
    "manhattan": "/assets/images/manhattan.png",
    "cosine":  "/assets/images/cosine.png",
    "jensen-shanon":  "/assets/images/jensen.png",
}

SOLAR_TOOLTIP_DELAY_TIMINGS = {
    "show": 600,
    "hide": 750,
}


METRIC_MEASURE_LOOKUP = {
    "euclidean": "RSSE",
    "manhattan": "MAE",
    "cosine": "Distance",
    "jensen-shanon": "Distance",
    "pct diff": "%",
}
METRIC_TOOLTIP_DECIMAL_ROUNDING = {
    "euclidean": 0,
    "manhattan": 0,
    "cosine": 2,
    "jensen-shanon": 2,
    "pct diff": 0,
}
TOOLTIP_LOST_ENERGY_DECIMAL_ROUNDING = 0

TORNADO_TOOLTIP_CODE_ALL_MISSING = "EMP"
TORNADO_TOOLTIP_SYMBOL_MISSING = -999
TORNADO_TOOLTIP_CODE_THIS_MISSING = "Miss"

TORNADO_TOOLTIP_CODE_DESCRIPTIONS = {
    TORNADO_TOOLTIP_CODE_ALL_MISSING: f"{TORNADO_TOOLTIP_CODE_ALL_MISSING} = all data for dates are empty.",
    TORNADO_TOOLTIP_SYMBOL_MISSING: f"{TORNADO_TOOLTIP_SYMBOL_MISSING} = some data are empty.",
    TORNADO_TOOLTIP_CODE_THIS_MISSING: f"{TORNADO_TOOLTIP_CODE_THIS_MISSING} = only this datum is empty.",
}

# Historical Weather Station

HISTORICAL_WS_RENAMED_COLUMN_LOOKUP = {
    "plant": "Plant",
    "GHI (solar anywhere)": "GHI SA (kWh/m²)",
    "SA TMY GHI": "SA Typical GHI Year (kWh/m²)",
    "PAMA TMY GHI": "PAMA Budget GHI (kWh/m²)",
    "Variance to Mean": "Variance to PAMA (%)",
    "Probability of Exceedance": "Probability of Exceedance",
}

HISTORICAL_WS_COLUMNS_WITH_COMMA_FORMAT = [
    "GHI SA (kWh/m²)",
    "SA Typical GHI Year (kWh/m²)",
    "PAMA Budget GHI (kWh/m²)",
]

# Make sure these two lookup dicts have the same keys
HISTORICAL_WS_SCALE_COLUMN_LOOKUP = {
    "GHI (solar anywhere)": 1,
    "SA TMY GHI": 1,
    "PAMA TMY GHI": 1,
    "Variance to Mean": 100,  # "Variance to PAMA" needs to be in percent, so we multiply by 100
}
HISTORICAL_WS_ROUNDING_COLUMN_LOOKUP = {
    "GHI (solar anywhere)": 0,
    "SA TMY GHI": 0,
    "PAMA TMY GHI": 0,
    "Variance to Mean": 1,
}

HISTORICAL_WS_COLUMN_FORMATTERS = {
    col: dict(type='numeric')
    for col in [
        "GHI (solar anywhere)",
        "SA TMY GHI",
        "PAMA TMY GHI",
    ]
}
HISTORICAL_WS_YEAR_TMY_VALUE = 1  # this number is set when data is run; cannot be NaN
MONTH_FULL_NAME_LOOKUP = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}
QUARTER_FULL_NAME_LOOKUP = {
    1: "Q1",
    2: "Q2",
    3: "Q3",
    4: "Q4",
}

SOLAR_DRILLED_DOWN_CHART_HEIGHT = 750

SOLAR_INVERTER_METRIC_UNITS_LOOKUP = {
    "lost_revenue": "$",
    "lost_energy": "MWh",
    "relative_deviation": "",
    "recovery": "%",
}
