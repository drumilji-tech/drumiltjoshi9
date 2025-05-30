import os
from config import get_environment_config

# Set environment variables from config
config = get_environment_config()
for key, value in config.items():
    os.environ[key] = value

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State

from app import app
from Model.DataAccess import Databricks_Repository
from Utils.Components import (
    gen_date_intervals,
    gen_sticky_header,
    generate_custom_date_range_selection_options,
)
from Utils.UiConstants import (
    HIDDEN_STYLE,
    VISIBLE_STYLE,
    DATE_PRESET_SELECTION_VALUE_DELIMITER,
)

server = app.server


NAV_ITEM_WIDTH_LOOKUP = {
    "wind": [
        "weather-station",
        "inverter-performance",
        "historical-weather-station",
        "performance-and-reliability",
        "fault-analysis",
    ],
    "solar": [
        "performance-and-reliability",
        "fault-analysis",
        "weather-station",
        "historical-weather-station",
        "inverter-performance",
    ],
}
WIND_PAGES = (
    "performance-and-reliability",
    "fault-analysis",
)
SOLAR_PAGES = (
    "weather-station",
    "inverter-performance",
    "historical-weather-station",
)

def entry_layout():
    # if in Wind mode, ensure we get min and max dates from `load_treemap_dataset()`
    conn = Databricks_Repository()
    min_date, max_date = conn.get_date_range()
    date_intervals = gen_date_intervals(
        min_date=min_date,
        max_date=max_date,
    )

    sticky_header = gen_sticky_header(
        date_intervals=date_intervals,
        registry_values=dash.page_registry.values(),
    )
    return dbc.Container(
        id="main-container",
        fluid=True,
        class_name="wrap",
        children=[
            dcc.Store(
                id="date-intervals-store",
                data=date_intervals,
            ),
            dcc.Store(
                id="last-pathname-navigated",
                data=None,
            ),
            dcc.Interval(id="periodic-connection", interval=1000 * 60 * 5),  # Ping every 5 minutes
            html.Div(id="empty-container"),
            sticky_header,
            dash.page_container,
        ],
    )


# this is a constant that should always mirror the order
# of Outputs(...) in the `toggle_global_controls` callback
CALLBACK_OUTPUTS_ORDER = [
    "performance-and-reliability",
    "fault-analysis",
    "weather-station",
    "inverter-performance",
    "historical-weather-station",
]

app.layout = entry_layout()


@app.callback(
    Output("empty-container", "children"),
    Input("periodic-connection", "n_intervals")
)
def establish_periodic_connection(n):
    """Ping the database every few minutes to ensure the app remains running."""
    conn = Databricks_Repository()
    conn.get_date_range()
    return dash.no_update

# this must match the --page-background-color variable in the CSS
PAGE_BACKGROUND_COLOR = "#111"

@app.callback(
    Output("header-first-row", "style"),
    Output("date-selector-box", "style"),
    Output("main-container", "style"),
    Output("nav-item-performance-and-reliability", "style"),
    Output("nav-item-fault-analysis", "style"),
    Output("nav-item-weather-station", "style"),
    Output("nav-item-inverter-performance", "style"),
    Output("nav-item-historical-weather-station", "style"),
    Output("nav-item-performance-and-reliability", "width"),
    Output("nav-item-fault-analysis", "width"),
    Output("nav-item-weather-station", "width"),
    Output("nav-item-inverter-performance", "width"),
    Output("nav-item-historical-weather-station", "width"),
    Input("url", "pathname"),
)
def toggle_global_controls(pathname):
    parsed_pathname = dash.strip_relative_path(pathname)
    if parsed_pathname in (None, "", "wind", "solar"):
        # All Splash Pages - Wind, Solar, and Root one
        return (
            HIDDEN_STYLE,
            HIDDEN_STYLE,
            {"background-color": "rgba(0,0,0,0)"},
            HIDDEN_STYLE,
            HIDDEN_STYLE,
            HIDDEN_STYLE,
            HIDDEN_STYLE,
            HIDDEN_STYLE,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    elif parsed_pathname in ("performance-and-reliability", "fault-analysis"):
        # Wind Pages
        width_values = [
            {"size": 1, "order": NAV_ITEM_WIDTH_LOOKUP["wind"].index(name) + 1}
            for name in CALLBACK_OUTPUTS_ORDER
        ]
        return (
            VISIBLE_STYLE,
            VISIBLE_STYLE,
            {"background-color": PAGE_BACKGROUND_COLOR},
            VISIBLE_STYLE,
            VISIBLE_STYLE,
            HIDDEN_STYLE,
            HIDDEN_STYLE,
            HIDDEN_STYLE,
            *width_values
        )
    else:
        width_values = [
            {"size": 1, "order": NAV_ITEM_WIDTH_LOOKUP["solar"].index(name) + 1}
            for name in CALLBACK_OUTPUTS_ORDER
        ]
        if parsed_pathname == "historical-weather-station":
            date_selector_style = HIDDEN_STYLE
        else:
            date_selector_style = VISIBLE_STYLE

        # Solar Pages
        return (
            VISIBLE_STYLE,
            date_selector_style,
            {"background-color": PAGE_BACKGROUND_COLOR},
            HIDDEN_STYLE,
            HIDDEN_STYLE,
            VISIBLE_STYLE,
            VISIBLE_STYLE,
            VISIBLE_STYLE,
            *width_values
        )

def gen_wind_project_options():
    conn = Databricks_Repository()
    plant_names = conn.get_wind_plants(is_sorted=True)
    project_list = plant_names
    project_list.insert(0, "All")

    project_dropdown_options = []
    for plant in project_list:
        label = plant
        value = plant
        project_dropdown_options.append({"label": label, "value": value})
    return project_dropdown_options

def gen_solar_project_options():
    conn = Databricks_Repository()
    plant_names = conn.get_plants(is_sorted=True)
    project_list = plant_names
    project_list.insert(0, "All")

    self_performing_plants = conn.get_self_perform_plants()
    project_dropdown_options = []
    for plant in project_list:
        label = plant
        value = plant
        if plant in self_performing_plants:
            label += " (SPC)"
        project_dropdown_options.append({"label": label, "value": value})
    return project_dropdown_options

@app.callback(
    Output("date-picker-range", "min_date_allowed"),
    Output("date-picker-range", "max_date_allowed"),
    Output("date-picker-range", "initial_visible_month"),
    Output("date-picker-range", "start_date"),
    Output("date-picker-range", "end_date"),
    Output("custom-date-range-selections", "value"),
    Output("custom-date-range-selections", "options"),
    Output("last-pathname-navigated", "data"),
    Output("project-dropdown", "options"),
    Input("url", "pathname"),
    State("last-pathname-navigated", "data"),
)
def update_global_date_picker(pathname, last_pathname):
    """Update the date selector based on if you're in Wind mode or Solar mode."""
    # Clean up the pathnames
    if pathname is not None:
        pathname = pathname.replace("/", "")
    if last_pathname is not None:
        last_pathname = last_pathname.replace("/", "")

    if any([page in pathname for page in WIND_PAGES]) and last_pathname not in WIND_PAGES:
        conn = Databricks_Repository()
        min_date, max_date = conn.get_wind_date_range()
        date_intervals = gen_date_intervals(
            min_date=min_date,
            max_date=max_date,
        )
        min_date_allowed = date_intervals[0]
        max_date_allowed = date_intervals[-1]
        initial_visible_month = date_intervals[-1]
        start_date = date_intervals[-30]
        end_date = date_intervals[-1]

        date_range_preset_options = generate_custom_date_range_selection_options(
            date_intervals=date_intervals,
        )
        project_options = gen_wind_project_options()
        return (
            min_date_allowed,
            max_date_allowed,
            initial_visible_month,
            start_date,
            end_date,
            date_range_preset_options[0]["value"],
            date_range_preset_options,
            pathname,
            project_options,
        )
    elif any([page in pathname for page in SOLAR_PAGES]) and last_pathname not in SOLAR_PAGES:
        conn = Databricks_Repository()
        min_date, max_date = conn.get_date_range()
        date_intervals = gen_date_intervals(
            min_date=min_date,
            max_date=max_date,
        )
        min_date_allowed = date_intervals[0]
        max_date_allowed = date_intervals[-1]
        initial_visible_month = date_intervals[-1]
        start_date = date_intervals[-30]
        end_date = date_intervals[-1]

        date_range_preset_options = generate_custom_date_range_selection_options(
            date_intervals=date_intervals,
        )

        project_options = gen_solar_project_options()
        return (
            min_date_allowed,
            max_date_allowed,
            initial_visible_month,
            start_date,
            end_date,
            date_range_preset_options[0]["value"],
            date_range_preset_options,
            pathname,
            project_options,
        )
    else:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            last_pathname,
            dash.no_update,
        )

@app.callback(
    Output("filter-faults-box", "style"),
    Output("acknowledged-fault-descriptions-box", "style"),
    Output("oem-dropdown-box", "style"),
    Output("project-dropdown-box", "style"),
    Input("url", "pathname"),
)
def toggle_fault_controls(pathname):
    parsed_pathname = dash.strip_relative_path(pathname)
    if parsed_pathname == "fault-analysis":
        return [VISIBLE_STYLE] * 4
    elif parsed_pathname not in ("", "wind", "solar", "historical-weather-station"):
        return [HIDDEN_STYLE] * 3 + [VISIBLE_STYLE]
    else:
        return [HIDDEN_STYLE] * 4


@app.callback(
    Output("collapsible-components", "className"),
    Input("toggle-top-panel-btn", "n_clicks"),
    State("collapsible-components", "className"),
    prevent_initial_callback=True,
)
def collapse_sticky_header(n, cls):
    if n is None:
        return dash.no_update
    if cls == "":
        return "collapsed-top-panel"
    return ""

@app.callback(
    Output("date-picker-range", "start_date", allow_duplicate=True),
    Output("date-picker-range", "end_date", allow_duplicate=True),
    Input("custom-date-range-selections", "value"),
    prevent_initial_call=True,
)
def update_calendar_picker_with_preset(value):
    split_val = value.split(DATE_PRESET_SELECTION_VALUE_DELIMITER)
    if len(split_val) == 1:
        return dash.no_update
    return split_val[0], split_val[1]

@app.callback(
    Output("project-dropdown", "className"),
    Input("self-perform-checkbox", "value"),
)
def toggle_self_perform_plant_controls(value):
    if value not in (None, "", []):
        return "disabled-strong"
    return ""

if __name__ == "__main__":
    app.run(
        debug=True,
        dev_tools_ui=True,
    )
