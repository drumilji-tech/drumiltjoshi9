"""The UI Components of the app."""

import math
from datetime import datetime, timedelta

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html, dash_table

from Model.DataAccess import Databricks_Repository
from Utils.Constants import (
    DEFAULT_PARSE_FUNCS,
    OEM_PROJECT_MAPPING,
)
from Utils.ISightConstants import (
    INIT_TORNADO_POINTS,
)
from Utils.Transformers import (
    get_projects,
)
from Utils.UiConstants import (
    HIDDEN_STYLE,
    VISIBLE_STYLE,
    APP_TITLE,
    DATE_PRESET_SELECTION_VALUE_DELIMITER,
)


def gen_project_dropdown():
    """Create an empty project dropdown component."""
    project_dropdown = dcc.Dropdown(
        id="project-dropdown",
        className="dropdown-proj",
        options=[{"label": "All", "value": "All"}],
        value="All",
        clearable=False,
    )
    return project_dropdown


def gen_date_intervals(min_date, max_date):
    """Create a daily sequence of dates for the date slider.
    
    Args:
        min_date (datetime|str): The minimum date for the slider.
        max_date (datetime|str): The maximum date for the slider.
    Returns:
        (pandas.DatetimeIndex): A Pandas DatetimeIndex.
    """  
    if isinstance(min_date, datetime):
        min_date = min_date.strftime("%Y-%m-%d")
    if isinstance(max_date, datetime):
        max_date = max_date.strftime("%Y-%m-%d")

    slider_dates = pd.date_range(
        min_date,
        max_date,
        freq="D",
    )
    date_intervals = pd.date_range(
        start=min(slider_dates), end=max(slider_dates), freq="1D"
    )
    
    return date_intervals


def acknowledge_control(
    _id, label=None, placeholder=None, as_children=None, fluid_width=None, style=None,
):
    """A widget that is meant to filter out data in other charts.

    Sometimes when you are looking at a chart and see visual pieces that
    stem from one attribute in the underlying dataset, it can clog up the
    chart, hiding other attributes from plain sight.

    This component is part of a system that, when hooked up, can allow you
    to stop seeing particular attributes so you can bring those hidden
    attributes front and center.

    In this application, the attribute that we don't want to see or NOT see
    are the Fault Codes.
        If one Fault Code were to contribute to 90% of the tiles in a treemap,
        we would like to easily hide or 'acknowledge' those tiles and see the
        contributes of the other Fault Codes.

    By populating this widget's dropdown with all the values of a given
    attribute, and by hooking it up to our desired charts, we can improve
    the user's analysis of the underlying data.

    Args:
        _id (str): The id of the `dcc.Dropdown` in this control.
        label (str): The label of the control.
        placeholder (str): The placholder string that appears in the dropdown.
        as_children (bool): See the Returns section.
        fluid_width (bool): If True, the dropdown will fill up the width
            of its parent. If False, it will be fixed as a wide dropdown.
        style (dict, optional): Style the acknowledge control with CSS.

    Returns:
        (html.Div): The control with a label and dropdown. The `as_children`
            param determines if the output is a raw list of the components
            (True) or whether it is wrapped in an `html.Div` (False).
    """
    if label is None:
        label = "Turbines to Hide"
    if placeholder is None:
        placeholder = "Add Turbine Codes to hide from the treemap view..."
    if as_children is None:
        as_children = False
    if fluid_width is None or fluid_width is False:
        dropdown_cls = "acknowledged-pp-turbines"
    else:
        dropdown_cls = ""
    if style is None:
        style = {}

    children = [
        html.Label(
            className="dropdown-label",
            htmlFor="acknowledged-pp-turbines",
            children=label,
        ),
        dcc.Dropdown(
            id=_id,
            className=dropdown_cls,
            value=[],
            placeholder=placeholder,
            multi=True,
            persistence=True,
            persistence_type="local",
        ),
    ]
    if as_children:
        return children
    return html.Div(children=children, style=style)


def gen_table_component(_id, table_columns):
    """Make a AEP table that sits inside a chart.

    The table only appears to float inside the chart because
    of the magic of CSS.

    Args:
        _id (str): The unique ID of the dash_table.DataTable contained.
    Returns:
        (html.Div): A Div that contains a dash table.

    """
    cell_height = 16
    component = html.Div(
        children=dash_table.DataTable(
            id=_id,
            columns=[{"id": c, "name": c} for c in table_columns],
            style_header={
                "backgroundColor": "rgb(30, 30, 30)",
                "color": "white",
            },
            style_data={
                "backgroundColor": "rgb(50, 50, 50)",
                "color": "white",
            },
            style_cell={
                "textAlign": "center",
                "height": f"{cell_height}px",
            },
        ),
    )
    return component

def gen_spotlight_component(measurement):
    """A widget meant to control the number of visible tornado bars.

    This component is intended to target a particular tornado chart
    in the UI. It is meant to be placed near the targeted chart.

    Args:
        measurement (str): Determines which tornado
            chart to affect. Can be either "ghi",
            "poa" or "bom".

    Returns:
        (list): A list of Dash (html, dcc) components
            meant as members of a container's `children`.
    """
    return [
        html.Span("Spotlight on the top "),
        dcc.Input(id=f"{measurement}-top-n-values", type="number", value=INIT_TORNADO_POINTS),
        html.Span(" Points"),
        html.Button(
            id=f"{measurement}-spotlight-btn",
            className="download-btn spotlight-btn",
            children="Update",
        ),
    ]

def is_this_week_present(date_intervals):
    """Determine if any available data exists this week."""
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday())  # Monday of this week
    end_of_week = start_of_week + timedelta(days=6)  # Sunday of this week
    is_this_week_present = any(start_of_week <= date <= end_of_week for date in date_intervals)
    return is_this_week_present

def is_last_week_present(date_intervals):
    """Determine if any available data exists for last week."""
    today = datetime.today()
    start_of_last_week = today - timedelta(days=today.weekday() + 7)  # Monday of last week
    end_of_last_week = start_of_last_week + timedelta(days=6)  # Sunday of last week
    is_last_week_present = any(start_of_last_week <= date <= end_of_last_week for date in date_intervals)
    return is_last_week_present

def is_this_month_present(date_intervals):
    """Determine if any available data exists for this month."""
    today = datetime.today()
    start_of_this_month = today.replace(day=1)  # First day of this month
    # Calculate the last day of this month
    end_of_this_month = (start_of_this_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    is_this_month_present = any(start_of_this_month <= date <= end_of_this_month for date in date_intervals)
    return is_this_month_present

def is_last_month_present(date_intervals):
    """Determine if any available data exists for last month."""
    today = datetime.today()
    # Calculate the first and last day of the previous month
    start_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    end_of_last_month = today.replace(day=1) - timedelta(days=1)
    is_last_month_present = any(start_of_last_month <= date <= end_of_last_month for date in date_intervals)
    return is_last_month_present

def generate_date_option_lookup(date_intervals):
    """Generate a lookup dict for date range options based on available data."""
    # Ensure date_intervals is sorted
    date_intervals = sorted(date_intervals)
    min_date = date_intervals[0]
    max_date = date_intervals[-1]
    today = datetime.today()
    
    # Calculate date ranges
    start_of_this_week = max(min_date, today - timedelta(days=today.weekday()))
    end_of_this_week = min(max_date, start_of_this_week + timedelta(days=6))

    start_of_last_week = max(min_date, start_of_this_week - timedelta(days=7))
    end_of_last_week = min(max_date, start_of_last_week + timedelta(days=6))

    start_of_this_month = max(min_date, today.replace(day=1))
    end_of_this_month = min(max_date, (start_of_this_month + timedelta(days=31)).replace(day=1) - timedelta(days=1))

    start_of_last_month = max(min_date, (start_of_this_month - timedelta(days=1)).replace(day=1))
    end_of_last_month = min(max_date, start_of_this_month - timedelta(days=1))

    # Updated Latest 7 Days range
    start_of_last_7_days = date_intervals[-7] if len(date_intervals) >= 7 else min_date
    end_of_last_7_days = date_intervals[-1]

    # Updated Latest 30 Days range
    start_of_last_30_days = date_intervals[-30] if len(date_intervals) >= 30 else min_date
    end_of_last_30_days = date_intervals[-1]

    options_lookup = {
        "Latest 30 Days": f"{start_of_last_30_days.date()}{DATE_PRESET_SELECTION_VALUE_DELIMITER}{end_of_last_30_days.date()}",
        "Latest 7 Days": f"{start_of_last_7_days.date()}{DATE_PRESET_SELECTION_VALUE_DELIMITER}{end_of_last_7_days.date()}",
        "This Week": f"{start_of_this_week.date()}{DATE_PRESET_SELECTION_VALUE_DELIMITER}{end_of_this_week.date()}",
        "Last Week": f"{start_of_last_week.date()}{DATE_PRESET_SELECTION_VALUE_DELIMITER}{end_of_last_week.date()}",
        "This Month": f"{start_of_this_month.date()}{DATE_PRESET_SELECTION_VALUE_DELIMITER}{end_of_this_month.date()}",
        "Last Month": f"{start_of_last_month.date()}{DATE_PRESET_SELECTION_VALUE_DELIMITER}{end_of_last_month.date()}",
        "All Available Days": f"{min_date.date()}{DATE_PRESET_SELECTION_VALUE_DELIMITER}{max_date.date()}",
    }

    return options_lookup

def generate_custom_date_range_selection_options(date_intervals):
    """Make custom presets dropdown to easily select dates."""
    date_option_lookup = generate_date_option_lookup(date_intervals)
    date_range_preset_options = [
        {"label": label, "value": date_option_lookup[label], "disabled": False}
        for label in [
            "Latest 30 Days",
            "Latest 7 Days",
            "This Week",
            "Last Week",
            "This Month",
            "Last Month",
            "All Available Days",
        ]
    ]
    for idx, option in enumerate(date_range_preset_options):
        if option["label"] == "This Week" and not is_this_week_present(date_intervals):
            date_range_preset_options[idx]["disabled"] = True
        elif option["label"] == "Last Week" and not is_last_week_present(date_intervals):
            date_range_preset_options[idx]["disabled"] = True
        elif option["label"] == "This Month" and not is_this_month_present(date_intervals):
            date_range_preset_options[idx]["disabled"] = True
        elif option["label"] == "Last Month" and not is_last_month_present(date_intervals):
            date_range_preset_options[idx]["disabled"] = True
    return date_range_preset_options

def gen_sticky_header(date_intervals, registry_values):
    """Generate the app's header with logo, title, and controls.

    The first thing you see when visit this app is the header
    at the top of the page. This header is special because it
    stays fixed and hovering above the rest of the app as you scroll
    up and down the page.

    The reason why this header sticks to the top is because it contains
    global controls (eg. dropdown(s)) that affect all charts in the app.
    You may want to scroll down with the global controls in sights so
    you can conveniently make change in the control and see your chart
    update in real time.

    Args:
        date_intervals (pandas.DateRange): A series of dates that are used
            to generate a time date ranger slider in the header.
        registry_values (odict_values): Should be equal to the output of
            `dash.page_registry.values()`. This param is used to setup
            navigation to helper users move between different pages of
            this multi-page app.

    Returns:
        (dash.html.Div Component): A UI component for the app.

    Raises:
        None
    """
    project_dropdown = gen_project_dropdown()

    # determine which date range presets are available or not
    date_option_lookup = generate_date_option_lookup(date_intervals)
    date_range_preset_options = [
        {"label": label, "value": date_option_lookup[label], "disabled": False}
        for label in [
            "Latest 30 Days",
            "Latest 7 Days",
            "This Week",
            "Last Week",
            "This Month",
            "Last Month",
            "All Available Days",
        ]
    ]
    for idx, option in enumerate(date_range_preset_options):
        if option["label"] == "This Week" and not is_this_week_present(date_intervals):
            date_range_preset_options[idx]["disabled"] = True
        elif option["label"] == "Last Week" and not is_last_week_present(date_intervals):
            date_range_preset_options[idx]["disabled"] = True
        elif option["label"] == "This Month" and not is_this_month_present(date_intervals):
            date_range_preset_options[idx]["disabled"] = True
        elif option["label"] == "Last Month" and not is_last_month_present(date_intervals):
            date_range_preset_options[idx]["disabled"] = True

    # make all four nav navigation buttons
    nav_contents = []
    for page in registry_values:
        if page["title"] and "iSight" not in page["title"]:

            clsname = ""
            _id = page["relative_path"].replace("/", "").lower()
            navitem = dbc.NavItem(
                dbc.NavLink(
                    id=_id,
                    className=clsname,
                    children=page["title"],
                    href=page["relative_path"],
                    active="exact",
                ),
            )
            nav_contents.append(navitem)

    nav_columns = [
        dbc.Col(
            id=f"nav-item-{nav_contents[idx].children.id}",
            style=VISIBLE_STYLE,
            width={"size": 2, "order": 1},
            children=nav_contents[idx],
        ) for idx in range(len(nav_contents))
    ]

    oem_dropdonwn_options = [{"label": "All", "value": "All"}]
    for key in list(OEM_PROJECT_MAPPING.keys()):
        oem_dropdonwn_options.append({
            "label": key,
            "value": key,
            "title": ", ".join(OEM_PROJECT_MAPPING[key]),
        })
    return html.Div(
        className="preheader",
        children=[
            dcc.Location(id="url"),
            dbc.Row(
                className="g-0",
                align="center",
                justify="between",
                children=[
                    dbc.Col(
                        id="logo-title-collapser-box",
                        md=5,
                        children=[
                            dcc.Link(
                                children=html.Img(
                                    id="spc-logo-container",
                                    style={
                                        "height": "1.65rem",
                                        "margin-right": "15px",
                                    },
                                    src=dash.get_asset_url(
                                        "spc_user_logo_transparent.png"
                                    ),
                                ),
                                href=dash.get_relative_path("/"),
                            ),
                            dbc.NavbarBrand(APP_TITLE, className="ms-2"),
                            html.Button(
                                id="toggle-top-panel-btn",
                                children="⋮",
                                className="toggle-top-panel-btn",
                            ),
                        ],
                    ),
                    *nav_columns,
                ],
            ),
            html.Div(
                id="collapsible-components",
                className="",
                children=[
                    dbc.Row(
                        id="header-first-row",
                        align="center",
                        justify="end",
                        children=[
                            dbc.Col(
                                id="filter-faults-box",
                                children=[
                                    *acknowledge_control(
                                        _id="filter-faults-dropdown",
                                        label="Filter by Fault",
                                        placeholder="Select fault codes to display...",
                                        as_children=True,
                                        fluid_width=True,
                                    )
                                ],
                                width=4,
                            ),
                            dbc.Col(
                                id="acknowledged-fault-descriptions-box",
                                children=[
                                    *acknowledge_control(
                                        _id="acknowledged-fault-descriptions",
                                        label="Acknowledge Faults",
                                        placeholder="Type to find faults (exclude)...",
                                        as_children=True,
                                        fluid_width=True,
                                    )
                                ],
                                width=4,
                            ),
                            dbc.Col(
                                id="oem-dropdown-box",
                                children=[
                                    html.Label(
                                        className="oem-dropdown-label",
                                        htmlFor="oem-dropdown",
                                        children="Filter by OEM",
                                    ),
                                    dcc.Dropdown(
                                        id="oem-dropdown",
                                        options=oem_dropdonwn_options,
                                        value="All",
                                        clearable=False,
                                    ),
                                ],
                                className="",
                                width=2,
                            ),
                            dbc.Col(
                                id="date-selector-box",
                                children=[
                                    dcc.Dropdown(
                                        id="custom-date-range-selections",
                                        clearable=False,
                                    ),
                                    dcc.DatePickerRange(
                                        id="date-picker-range",
                                        className="",
                                    ),
                                ],
                                className="",
                                width=4,
                            ),
                            dbc.Col(
                                id="project-dropdown-box",
                                children=[
                                    html.Label(
                                        id="project-dropdown-label",
                                        className="project-dropdown-label",
                                        htmlFor="project-dropdown",
                                        children=[
                                            html.Span("Filter by Project"),
                                            dcc.Checklist(
                                                id="self-perform-checkbox",
                                                style={"lineHeight": "34px"},
                                                options=["Self-Perform"],
                                                value=[],
                                                labelStyle={"display": "inline-block"},
                                            ),
                                        ]
                                    ),
                                    project_dropdown,
                                ],
                                width=2,
                            ),
                        ],
                    ),
                ]
            ),
        ],
    )
