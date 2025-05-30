##my code changes for performance.py

import time
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import ctx, dcc, html, callback, Input, Output, State

from Charts.Heatmap import (
    generate_comp_temp_heatmap,
    make_styled_heatmap_multiindex,
    generate_intra_heatmap,
)
from Charts.Plotters import default_chart
from Charts.PowerCurve import (
    gen_power_curve_subchart_databricks,
    gen_peer_to_peer_chart,
)
from Charts.Solar.Inverters import (
    gen_inverters_number_line,
)
from Charts.Treemap import (
    gen_comp_temp_scatterplot,
    generate_power_performance_treemap_databricks,
    generate_transformer_treemap
)
from Charts.PowerCurve import (
    calculate_weighted_average_power_by_turbine,
    full_calculate_AEP,
    find_common_valid_indices,
)
from Charts.Yaw import generate_yaw_chart
from Model.DataAccess import Databricks_Repository
from Utils.Constants import DEFAULT_PARSE_FUNCS, TRANSFORMER_COMPONENTS
from Utils.Components import (
    acknowledge_control,
    gen_table_component,
)
from Utils.Loaders import (
    load_treemap_dataset,
    load_power_curve_data,
    load_power_distribution_data,
    load_ws_distribution_data,
    load_surrogation_strategies,
)
from Utils.Transformers import (
    format_date_for_filename,
    filter_treemap_columns,
    filter_lost_energy,
    filter_mean_values,
    format_columns,
)
from Utils.UiConstants import (
    PERFORMANCE_METRICS,
    POWER_PERFORMANCE_TREEMAP_OPTIONS,
    COMPONENT_TEMPERATURE_HEATMAP_DEFAULT_SORTING,
)
from Utils.Enums import (
    ComponentTypes
)

TOOLTIP_DELAY_TIMINGS = {
    "show": 600,
    "hide": 750,
}
TOOLTIP_TEXT_LOOKUP = {
    PERFORMANCE_METRICS[0]: (
        "The amount of money lost or gained relative to what was expected "
        "from the turbine over the selected period of time. The cost per "
        "MWh varies every month and for every site."
    ),
    PERFORMANCE_METRICS[1]: (
        "The amount of energy, in MWh, that is not generated relative to "
        "what was expected from the turbine over the selected period of "
        "time. No other variables influence this metric.",
    ),
    PERFORMANCE_METRICS[2]: (
        "A measurement of the deviation in performance relative to the rest "
        "of the wind farm (and class) where the turbine belongs over the "
        "selected period of time. Higher severity indicates higher "
        "separation between actual and expected power than the other turbines "
        "in the site.",
    ),
}

def format_dates_for_title(start_date, end_date):
    """Convert Dates for Human Readable Titles.
    
    Args:
        start_date (str): A stringy datetime.
        end_date (str): A stringy datetime.
    
    Returns:
        start_str, end_str (tuple of str): A
            pair of formatted strings that
            represent the input dates.
    """
    start_date = start_date.split("T")[0]
    end_date = end_date.split("T")[0]
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    start_str = start.strftime("%b %d, %Y")
    end_str = end.strftime("%b %d, %Y")
    return start_str, end_str

def gen_placeholder_comp_temp_chart():
    fig = default_chart(bgcolor="#171717")
    fig.layout.height = 40
    return fig

dash.register_page(
    __name__,
    path="/performance-and-reliability",
    title="Performance and Reliability",
)


def layout():
    component_temperature_graph = dcc.Graph(
        id="treemap",
        className="treemap",
        figure=default_chart(),
        clear_on_unhover=True,
        mathjax=True,
    )

    # Transformer Treemap and Subcharts
    transformer_reliability = dcc.Graph(id="tr-treemap", className="tr-treemap",
                                        figure=default_chart())
    transformer_temp_heatmap_chart = dcc.Graph(
        id="tr-temp-heatmap",
        figure=default_chart(bgcolor="#171717"),
        config={"displayModeBar": False},
    )
    transformer_heatmap_box = html.Div(
        id="tr-heatmap-box",
        className="is-closed",
        children=[
            transformer_temp_heatmap_chart,
        ],
    )

    # Component Temperature Treemap and Sub-Charts
    temp_heatmap_chart = dcc.Graph(
        id="temp-heatmap",
        figure=gen_placeholder_comp_temp_chart(),
        config={"displayModeBar": False},
    )
    heatmap_box_container = html.Div(
        style={
            "backgroundColor": "#171717",
            "borderRadius": "8px",
            "padding": "0.5rem",
        },
        children=[
            dcc.RadioItems(
                id="heatmap-toggle",
                className="heatmap-toggle",
                options=[
                    {
                        "label": "By Turbine",
                        "value": "by-turbine",
                    },
                    {
                        "label": "By Component",
                        "value": "by-component",
                    },
                ],
                value=COMPONENT_TEMPERATURE_HEATMAP_DEFAULT_SORTING,
                labelStyle={"display": "inline-block"},
            ),
            temp_heatmap_chart,
        ],
    )
    heatmap_box = dcc.Loading(
        id="loading-comp-temp-heatmaps",
        type="graph",
        delay_show=0,
        overlay_style={
            "opacity": 0.7,
            "visibility":"visible",
            "filter": "blur(2px)",
        },
        children=[
            heatmap_box_container,
        ],
    )

    # Power Performance Chart and Sub-Charts
    power_performance_graph = dcc.Graph(id="pp-treemap", figure=default_chart())
    power_performance_numberline_graph = dcc.Graph(
        id="power-performance-number-line",
        figure=default_chart(),
    )
    pp_treemap_and_subcharts = html.Div(
        id="treemap-heatmap-box3",
        className="treemap-subcharts-container",
        children=[
            power_performance_graph,
            power_performance_numberline_graph,
            html.Div(
                id="heatmap-box3",
                className="is-closed",
                children=[
                    dcc.Tabs(
                        id="heatmap-toggle3",
                        className="heatmap-toggle",
                        value="level-1",
                        children=[
                            dcc.Tab(
                                label="Level 1",
                                value="level-1",
                                children=[
                                    dcc.Graph(
                                        id="level-1-subplot",
                                        figure=default_chart("#171717"),
                                    ),
                                ],
                            ),
                            dcc.Tab(
                                label="Level 2",
                                value="level-2",
                                children=[
                                    html.Span("Neighboring Turbines Shown"),
                                    dcc.Dropdown(
                                        id="neighbors-dropdown",
                                        multi=True,
                                    ),
                                    dcc.Graph(
                                        id="peer2peer-chart",
                                        figure=default_chart("#171717"),
                                    ),
                                    gen_table_component(
                                        _id="peer-to-peer-table",
                                        table_columns=("Pairings", "% AEP Delta"),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    output = [
        dcc.Download(id="temp-treemap-download-receiver"),
        dcc.Store(id="comp-temp-subcharts-are-visible", data=False),
        dcc.Store(id="power-perf-click-store", data=None),
        dcc.Store(id="start-date-clean2", data=None),
        dcc.Store(id="end-date-clean2", data=None),
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="title-and-controls",
                    children=[
                        html.Span(
                            id="pp-treemap-title",
                            className="chart-title",
                        ),
                        html.Div(
                            className="chart-control",
                            children=[
                                dbc.Tooltip(
                                    TOOLTIP_TEXT_LOOKUP[PERFORMANCE_METRICS[0]],
                                    target=PERFORMANCE_METRICS[0],
                                    placement="bottom",
                                    delay=TOOLTIP_DELAY_TIMINGS,
                                    class_name="metric-tooltip",
                                ),
                                dbc.Tooltip(
                                    TOOLTIP_TEXT_LOOKUP[PERFORMANCE_METRICS[1]],
                                    target=PERFORMANCE_METRICS[1],
                                    placement="bottom",
                                    delay=TOOLTIP_DELAY_TIMINGS,
                                    class_name="metric-tooltip",
                                ),
                                dbc.Tooltip(
                                    TOOLTIP_TEXT_LOOKUP[PERFORMANCE_METRICS[2]],
                                    target=PERFORMANCE_METRICS[2],
                                    placement="bottom",
                                    delay=TOOLTIP_DELAY_TIMINGS,
                                    class_name="metric-tooltip",
                                ),
                                dcc.RadioItems(
                                    id="sort-by",
                                    className="right-floating-control",
                                    options=POWER_PERFORMANCE_TREEMAP_OPTIONS,
                                    value=POWER_PERFORMANCE_TREEMAP_OPTIONS[0]["value"],
                                    labelStyle={"display": "inline-block"},
                                ),
                                dcc.RadioItems(
                                    id="under-over-perform",
                                    className="under-over-perform",
                                    options=[
                                        {
                                            "label": "Overperforming",
                                            "value": "overperforming",
                                        },
                                        {
                                            "label": "Underperforming",
                                            "value": "underperforming",
                                        },
                                    ],
                                    value="underperforming",
                                    labelStyle={"display": "inline-block"},
                                ),
                                acknowledge_control(_id="acknowledged-pp-turbines"),
                            ],
                        ),
                    ],
                ),
                pp_treemap_and_subcharts,
            ],
        ),
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="title-and-controls",
                    children=[
                        html.Span(
                            id="treemap-title",
                            className="chart-title",
                        ),
                        html.Div(
                            className="chart-control",
                            children=[
                                html.Button(
                                    id="download-temp-treemap-btn",
                                    className="download-btn",
                                    children="Download",
                                ),
                                html.Label(
                                    className="dropdown-label",
                                    htmlFor="component-dropdown",
                                    children="Filter By Component",
                                ),
                                dcc.Dropdown(
                                    id="component-dropdown",
                                    className="dropdown-comp",
                                    value="All",
                                    clearable=False,
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    className="card",
                    children=[
                        component_temperature_graph,
                        dcc.Tooltip(id="treemap-tooltip", direction="top"),
                        heatmap_box,
                    ],
                ),
            ],
        ),
        # ---- This is the section that holds all of the Transformer Reliability Functionality - Jylen Tate
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="title-and-controls",
                    children=[
                        html.Span(
                            id="tr-treemap-title",
                            className="chart-title",
                        ),
                        html.Div(
                            className="chart-control",
                            children=[
                                dcc.RadioItems(
                                    id="mean-dev-metric",
                                    className="mean-dev-metric",
                                    options=[
                                        {
                                            "label": html.Span("Mean", id="mean-option"),
                                            "value": "Mean",
                                        },
                                        {
                                            "label": html.Span("Intra", id="intra-option"),
                                            "value": "Intra",
                                        },
                                    ],
                                    value="Intra",
                                    inline=True,
                                ),
                                dbc.Tooltip(
                                    "The comparison of the deviation in temperature values using the three phases in a transformer.",
                                    target="intra-option",
                                    placement="top",
                                    delay=TOOLTIP_DELAY_TIMINGS,
                                ),
                                html.Button(
                                    id="download-temp-treemap-btn",
                                    className="download-btn",
                                    children="Download",
                                ),
                                html.Label(
                                    className="drop",
                                    htmlFor="transformer-component-dropdown",
                                    children="Filter By Transformer Type",
                                ),
                                dcc.Dropdown(
                                    id="transformer-component-dropdown",
                                    className="transformer-dropdown-comp",
                                    value="All",
                                    clearable=False,
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    id="treemap-heatmap-box_10",
                    className="treemap-subcharts-container",
                    children=[
                        transformer_reliability,
                        transformer_heatmap_box,
                    ],
                ),
            ],
        ),
        # ---
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="title-and-controls",
                    children=[
                        html.Span(
                            id="yaw-error-chart-title",
                            className="chart-title",
                        ),
                    ],
                ),
                dcc.Graph(
                    id="yaw-error-chart",
                    className="yaw-error-chart",
                    figure=default_chart(),
                ),
            ],
        ),
    ]
    return output


@callback(
    Output("treemap-tooltip", "show"),
    Output("treemap-tooltip", "bbox"),
    Output("treemap-tooltip", "children"),
    Input("treemap", "hoverData"),
)
def update_component_temperature_tooltip(hoverData):
    if hoverData is None:
        return False, dash.no_update, dash.no_update
    pt = hoverData["points"][0]
    bbox = pt["bbox"]

    # TODO: Read the hovertemplate from the figure, rather than guessing
    try:
        turbine = pt["customdata"][0]
    except:
        turbine = "NA"

    try:
        component = pt["customdata"][1]
    except IndexError:
        component = "NA"

    try:
        temp = pt["customdata"][2]
        temp = round(temp, 1)
    except IndexError:
        temp = "NA"

    try:
        park_avg_temp = pt["customdata"][3]
        park_avg_temp = round(park_avg_temp, 1)
    except IndexError:
        park_avg_temp = "NA"

    try:
        severity = pt["y"]
        severity = int(severity)
    except IndexError:
        severity = "NA"

    try:
        temp_diff = pt["x"]
        temp_diff = round(temp_diff, 1)
    except IndexError:
        temp_diff = "NA"

    # this blurb is unused for now, but will be used for later.
    std_dev_blurb = html.P(
        f"The temperature of {turbine}'s {component} component is ~___ std dev from the mean of all other {component}s."
    )
    children = [
        html.Div(
            [
                html.B(f"{turbine} {component}"),
                html.P(f"(Y-Axis) Severity: {severity}", style={"marginBottom": 0}),
                html.P(f"(X-Axis) Temp Deviation: {temp_diff}°C", style={"marginBottom": 0, "marginTop": 0}),
                html.P(f"  = {temp}°C (Temp) - {park_avg_temp}°C (Park Avg)", className="parenthetical", style={"marginTop": 0}),
            ],
            style={
                "width": "300px",
                "white-space": "normal",
            }
        ),
    ]
    return True, bbox, children

@callback(
    Output("start-date-clean2", "data"),
    Output("end-date-clean2", "data"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    State("date-intervals-store", "data"),
)
def store_dates(start_date, end_date, date_intervals_store):
    start_date = start_date.split("T")[0]
    start_date = datetime.strptime(start_date, "%Y-%m-%d")

    end_date = end_date.split("T")[0]
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    return start_date, end_date

@callback(
    Output("temp-treemap-download-receiver", "data"),
    Input("download-temp-treemap-btn", "n_clicks"),
    State("treemap", "figure"),
    State("project-dropdown", "value"),
    State("component-dropdown", "value"),
    State("start-date-clean2", "data"),
    State("end-date-clean2", "data"),
    prevent_initial_call=True,
)
def download_temperature_treemap_dataset(
        n_clicks,
        treemap_json,
        project,
        component,
        start_date,
        end_date,
):
    if n_clicks is None:
        return dash.no_update

    num_of_rows = 10
    customdata = treemap_json["data"][0]["customdata"]
    labels = treemap_json["data"][0]["labels"]
    project_arr = [l.split("<br>")[0].split("-")[0] for l in labels]
    turbine_arr = [l.split("<br>")[0].split("-")[1] for l in labels]
    component_arr = [l.split("<br>")[1] for l in labels]

    df_rows = []
    for k, temp_container in enumerate(customdata[:num_of_rows]):
        row = {}
        row["Project"] = project_arr[k]
        row["Turbine"] = turbine_arr[k]
        row["Component"] = component_arr[k]
        row["Temperature (°C)"] = temp_container[0]
        row["Park Average (°C)"] = temp_container[1]
        df_rows.append(row)
    df = pd.DataFrame(df_rows)

    start_date_fmt = format_date_for_filename(start_date)
    end_date_fmt = format_date_for_filename(end_date)

    project_fmt = project
    if project == "All":
        project_fmt = "all_projects"
    project_fmt = project_fmt.replace(" ", "")

    component_fmt = "_" + component
    if component == "All":
        component_fmt = ""
    filename = f"{start_date_fmt}_to_{end_date_fmt}_temperature_{project_fmt}{component_fmt}.xlsx"
    return dcc.send_data_frame(df.to_excel, filename, sheet_name="Sheet1")


@callback(
    Output("heatmap-box3", "className"),
    Output("treemap-heatmap-box3", "className"),
    Input("pp-treemap", "clickData"),
    Input("heatmap-toggle3", "value"),
    Input("start-date-clean2", "data"),
    Input("end-date-clean2", "data"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("project-dropdown", "value"),
    Input("under-over-perform", "value"),
    Input("sort-by", "value"),
    Input("acknowledged-pp-turbines", "value"),
    State("heatmap-box3", "className"),
    prevent_inital_call=True,
)
def toggle_power_performance_treemap_subcharts(
    treemapClickData,
    toggle,
    start_date,
    end_date,
    picker_start_date,
    picker_end_date,
    project_dropdown,
    under_over_perform,
    sort_by,
    acknowledged_pp_turbines,
    last_subchart_cls,
):
    subchart_cls = last_subchart_cls
    if ctx.triggered_id is None:
        return dash.no_update
    elif ctx.triggered_id == "pp-treemap":
        if last_subchart_cls == "is-closed":
            subchart_cls = "is-open"
        else:
            subchart_cls = "is-closed"
    elif ctx.triggered_id in (
        "date-picker-range",
        "project-dropdown",
        "under-over-perform",
        "sort-by",
        "acknowledged-pp-turbines",
    ):
        subchart_cls = "is-closed"

    if subchart_cls == "is-closed":
        treemap_cls = "treemap-subcharts-container"
        return subchart_cls, treemap_cls
    treemap_cls = "treemap-subcharts-container bottom-margin3"
    return subchart_cls, treemap_cls


@callback(
    Output("component-dropdown", "options"),
    Input("component-dropdown", "value"),
)
def populate_comp_temp_treemap_dropdown_options(value):
    conn = Databricks_Repository()
    isight_attributes = conn.get_wind_unique_turbine_isight_attributes()
    isight_temp_attributes = [attr for attr in isight_attributes if "temp" in attr.lower()]

    component_list = ["All"]
    component_list.extend(isight_temp_attributes)
    dropdown_options = [
        {"label": component, "value": component} for component in component_list
    ]
    return dropdown_options


# --- Populates the Transformer Reliability Component Dropdown Options
@callback(
    Output("transformer-component-dropdown", "options"),
    Input("mean-dev-metric", "value")
)
def populate_transformers_component_dropdown_options(value):
    dropdown_options = {}
    if value == "Mean":
        dropdown_options = [{"label": "All", "value": "All"}] + [
            {"label": component, "value": component} for component in TRANSFORMER_COMPONENTS
            if
            component != ComponentTypes.TRANSFORMER_CORE_PHASE_TEMP_DEV.value and component != ComponentTypes.TRANSFORMER_PHASE_TEMP_DEV.value
        ]
        return dropdown_options
    elif value == "Intra":
        dropdown_options = [{"label": "All", "value": "All"}] + [
            {"label": ComponentTypes.TRANSFORMER_CORE_PHASE_TEMP_DEV.value,
             "value": ComponentTypes.TRANSFORMER_CORE_PHASE_TEMP_DEV.value},
            {"label": ComponentTypes.TRANSFORMER_PHASE_TEMP_DEV.value,
             "value": ComponentTypes.TRANSFORMER_PHASE_TEMP_DEV.value}
        ]
        return dropdown_options

    return dropdown_options


@callback(
    Output("pp-treemap", "figure"),
    Output("pp-treemap-title", "children"),
    Output("power-performance-number-line", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("project-dropdown", "value"),
    Input("under-over-perform", "value"),
    Input("acknowledged-pp-turbines", "value"),
    Input("sort-by", "value"),
)
def update_power_performance_chart(
    start_date,
    end_date,
    project,
    under_over_perform,
    acknowledged_pp_turbines,
    sort_by,
):
    conn = Databricks_Repository()
    df_treemap = conn.get_wind_power_perforamnce_treemap_data(
        start_date=start_date,
        end_date=end_date,
        plant=project,
        acknowledged_pp_turbines=acknowledged_pp_turbines,
        under_over_perform=under_over_perform,
        is_filtered=True,
        sort_by=sort_by,
    )
    chart = generate_power_performance_treemap_databricks(
        data_frame=df_treemap,
        under_over_perform=under_over_perform,
        sort_by=sort_by,
    )

    df_numberline = conn.get_wind_power_perforamnce_treemap_data(
        start_date=start_date,
        end_date=end_date,
        plant=project,
        acknowledged_pp_turbines=acknowledged_pp_turbines,
        under_over_perform=under_over_perform,
        is_filtered=False,
    )
    number_line_chart = gen_inverters_number_line(
        data_frame=df_numberline,
        metric=sort_by,
        app_mode="wind",
    )

    start_str, end_str = format_dates_for_title(start_date, end_date)

    # count all items per trace
    pts_displayed_in_numberline = 0
    for trace in number_line_chart["data"]:
        pts_displayed_in_numberline += len(trace["x"])
    numberline_title = f"Displaying {pts_displayed_in_numberline} Turbines ({start_str} to {end_str})"
    number_line_chart.update_layout(title=numberline_title)

    title = [
        html.Span(
            children=f"Power Performance ",
            className="title",
        ),
        html.Span(
            children=f"({start_str} to {end_str})",
            className="subtitle",
        ),
    ]
    return chart, title, number_line_chart


@callback(
    Output("treemap-title", "children"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("component-dropdown", "value"),
    Input("project-dropdown", "value"),
)
def update_comp_temp_title(
    start_date,
    end_date,
    component_type,
    project,
):
    start_str, end_str = format_dates_for_title(start_date, end_date)
    title_pieces = ["Temperature Deviation of Turbine Components"]
    if component_type != "All":
        title_pieces.append(component_type)
    if project != "All":
        title_pieces.append(project)

    title = ", ".join(title_pieces)
    title += " "
    treemap_fig_title = [
        html.Span(
            children=title,
            className="title",
        ),
        html.Span(
            children=f"({start_str} to {end_str})",
            className="subtitle",
        ),
    ]
    return treemap_fig_title


@callback(
    Output("tr-treemap-title", "children"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
)
def update_transformer_title(
    start_date,
    end_date,
):
    start_str, end_str = format_dates_for_title(start_date, end_date)
    transformer_reliability_title = [
        html.Span(
            children=f"Transformer Reliability ",
            className="title",
        ),
        html.Span(
            children=f"({start_str} to {end_str})",
            className="subtitle",
        ),
    ]
    return transformer_reliability_title

@callback(
    Output("yaw-error-chart", "figure"),
    Output("yaw-error-chart-title", "children"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("project-dropdown", "value"),
)
def update_yaw_chart(start_date, end_date, project):
    # Generate the yaw chart
    conn = Databricks_Repository()
    yaw_error_data = conn.gen_wind_yaw_error_data_by_turbine(start_date, end_date)
    yaw_error_fig = generate_yaw_chart(yaw_error_data)

    # Update the title for Yaw Chart
    project_label = project if project != "All" else "All Projects"
    component_type = "All"
    comp_label = component_type if component_type != "All" else "All Components"
    subtitle = f"- {project_label}, {comp_label}"
    yaw_error_title = [
        html.Span(
            children=f"Yaw Error by Turbine ",
            className="title",
        ),
        html.Span(
            children=subtitle,
            className="subtitle",
        ),
    ]
    return yaw_error_fig, yaw_error_title

@callback(
    Output("treemap", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("component-dropdown", "value"),
    Input("project-dropdown", "value"),
)
def update_component_temp_visualization(
    start_date,
    end_date,
    component,
    project,
):
    conn = Databricks_Repository()
    data = conn.get_wind_component_temperature_data(
        start_date=start_date,
        end_date=end_date,
        plant=project,
        component=component,
    )
    fig = gen_comp_temp_scatterplot(data=data)
    return fig

@callback(
    Output("tr-treemap", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("project-dropdown", "value"),
    Input("transformer-component-dropdown", "value"),
    Input("mean-dev-metric", "value"),
)
def update_transformer_treemap(
    start_date,
    end_date,
    project,
    transformers_component,
    mean_dev_metric,
):
    treemap_data = load_treemap_dataset()

    # Generates the transformer reliability treemap
    transformer_fig = generate_transformer_treemap(
        treemap_data_from_file=treemap_data,
        mean_dev_metric=mean_dev_metric,
        start=start_date,
        end=end_date,
        component_type=transformers_component,
        project=project,
    )
    return transformer_fig

@callback(
    Output("acknowledged-pp-turbines", "options"),
    Input("url", "pathname"),
)
def populate_acknowledge_pp_turbine_options(pathname):
    parsed_pathname = dash.strip_relative_path(pathname)
    if parsed_pathname == "performance-and-reliability":
        conn = Databricks_Repository()
        turbines = conn.get_wind_all_unique_turbines()
        return turbines
    return dash.no_update


@callback(
    Output("temp-heatmap", "figure"),
    Output("comp-temp-subcharts-are-visible", "data"),
    Input("treemap", "clickData"),
    Input("heatmap-toggle", "value"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("project-dropdown", "value"),
    Input("component-dropdown", "value"),
    State("comp-temp-subcharts-are-visible", "data"),
    prevent_inital_call=True,
)
def update_component_temperature_heatmap_subchart(
    treemapClickData,
    heatmap_toggle,
    start_date,
    end_date,
    project_dropdown,
    component_dropdown,
    comp_temp_subcharts_are_open,
):
    if (
        treemapClickData is None
        or ctx.triggered_id is None
        or len(treemapClickData["points"]) <= 0
    ):
        return dash.no_update
    if (ctx.triggered_id == "heatmap-toggle" and comp_temp_subcharts_are_open is False):
        return dash.no_update

    global_control_changed = ctx.triggered_id in (
        "component-dropdown",
        "project-dropdown",
        "date-picker-range",
    )
    if (
        global_control_changed
        or (ctx.triggered_id == "heatmap-toggle" and comp_temp_subcharts_are_open is False)
    ):
        heatmap = gen_placeholder_comp_temp_chart()
        return heatmap, False

    customdata = treemapClickData["points"][0]["customdata"]
    project_turbine = customdata[0]
    component_type = customdata[1]

    if heatmap_toggle == "by-component":
        conn = Databricks_Repository()
        df_by_turbine = conn.get_wind_component_temperature_data_by_component(
            start_date=start_date,
            end_date=end_date,
            element_name=project_turbine,
        )
        heatmap = make_styled_heatmap_multiindex(
            z=df_by_turbine,
            element_name=project_turbine,
            component_type=component_type,
            heatmap_toggle=heatmap_toggle,
        )
        start_str, end_str = format_dates_for_title(start_date, end_date)
        heatmap.layout.title = f"All Components for Turbine {project_turbine} ({start_str} to {end_str})"
    elif heatmap_toggle == "by-turbine":
        conn = Databricks_Repository()
        df_by_turbine = conn.get_wind_component_temperature_data_by_turbine(
            start_date=start_date,
            end_date=end_date,
            component_type=component_type,
        )
        heatmap = make_styled_heatmap_multiindex(
            z=df_by_turbine,
            element_name=project_turbine,
            component_type=component_type,
            heatmap_toggle=heatmap_toggle,
        )
        start_str, end_str = format_dates_for_title(start_date, end_date)
        project_str = "all Turbines" if project_dropdown.lower() == "all" else f"{project_dropdown} Turbines"
        title = f"Component {component_type} across {project_str} ({start_str} to {end_str})"
        heatmap.layout.title = title
    return heatmap, True

@callback(
    Output("tr-temp-heatmap", "figure"),
    Output("tr-heatmap-box", "className"),
    Output("treemap-heatmap-box_10", "className"),
    Input("tr-treemap", "clickData"),
    Input("heatmap-toggle", "value"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("project-dropdown", "value"),
    Input("component-dropdown", "value"),
    State("tr-heatmap-box", "className"),
    Input("mean-dev-metric", "value"),
    prevent_inital_call=True,
)
def update_transformer_temp_heatmap(
        treemapClickData,
        heatmap_toggle,
        start_date,
        end_date,
        project_dropdown,
        component_dropdown,
        last_heatmap_cls,
        metric
):
    heatmap_cls = last_heatmap_cls
    if ctx.triggered_id is None:
        return dash.no_update
    elif ctx.triggered_id == "tr-treemap":
        # if treemap is clicked, hide/reveal the heatmap
        if last_heatmap_cls == "is-closed":
            heatmap_cls = "is-open"
        else:
            heatmap_cls = "is-closed"
    elif ctx.triggered_id in (
            "date-picker-range",
            "project-dropdown",
            "transformer-component-dropdown",
    ):
        heatmap_cls = "is-closed"

    if heatmap_cls == "is-closed":
        heatmap = default_chart(bgcolor="#171717")
        treemap_cls = "treemap-subcharts-container"
        return heatmap, heatmap_cls, treemap_cls

    label = treemapClickData["points"][0]["label"]
    project_turbine, component_type = label.split("<br>")
    project = project_turbine.split("-")[0]
    #turbine = project_turbine.split("-")[1]

    # --- Generates Heatmap based off Metric

    treemap_data = load_treemap_dataset()
    if metric == "Mean":
        mean_col_map = treemap_data.columns.str.endswith("_mean")
        dff = treemap_data.copy()
        dff = dff.loc[:, ~mean_col_map]
        dff = format_columns(dff)

        lost_energy_df = None
        dff = filter_treemap_columns(
            data_frame=dff,
            project=project,
            turbine=None,
            component_type=component_type,
        )

        lost_energy_df = filter_lost_energy(
            treemap_data.loc[:, ~mean_col_map], project
        )
        mean_df = filter_mean_values(treemap_data, project, component_type)

        treemap_cls = "treemap-subcharts-container bottom-margin3"
        heatmap = generate_comp_temp_heatmap(
            data_frame=dff, lost_energy_df=lost_energy_df, mean_frame=mean_df
        )
        return heatmap, heatmap_cls, treemap_cls

    elif metric == "Intra":
        dff = treemap_data.copy()
        treemap_cls = "treemap-subcharts-container bottom-margin3"
        heatmap = generate_intra_heatmap(dff, project)
        return heatmap, heatmap_cls, treemap_cls

    # --- Jylen Tate


@callback(
    Output("neighbors-dropdown", "options"),
    Output("neighbors-dropdown", "value"),
    Output("power-perf-click-store", "data"),
    Input("pp-treemap", "clickData"),
    State("heatmap-box3", "className"),
    State("start-date-clean2", "data"),
    State("end-date-clean2", "data"),
)
def load_neighbors_dropdown(
        treemapClickData,
        subchart_cls,
        start_date,
        end_date
):
    if not treemapClickData or subchart_cls == "is-open":
        return dash.no_update

    # figure out the name of the Turbine we clicked
    label = treemapClickData["points"][0]["label"]
    selected_target = label.split("<br>")[0]

    surrogation_strategies = load_surrogation_strategies()
    top_neighbors = surrogation_strategies[
        surrogation_strategies["target"] == selected_target
        ]
    top_neighbors = top_neighbors.nlargest(10, "bulk_R2")
    options = [
        {
            "label": f"{row['surrogate']} (R²: {row['bulk_R2']:.2f})",
            "value": row["surrogate"],
        }
        for index, row in top_neighbors.iterrows()
    ]
    power_curve_df = load_power_curve_data()
    distribution_df = load_power_distribution_data()

    power_curves = power_curve_df.loc[
        power_curve_df.index.get_level_values("Day") != "All"
        ]
    # Filter power curves based on selected date range and average over the days
    mask = (
                   pd.to_datetime(power_curves.index.get_level_values("Day")) >= start_date
           ) & (pd.to_datetime(power_curves.index.get_level_values("Day")) <= end_date)

    filtered_power_curves = power_curves.loc[mask]
    filtered_distribution = distribution_df[mask]

    values = []
    for option in options:
        if option["value"] in filtered_power_curves.index and selected_target in filtered_distribution.index:
            values.append(option["value"])

    values = values[0:3]
    return options, values, selected_target


@callback(
    Output("level-1-subplot", "figure"),
    Input("power-perf-click-store", "data"),
    State("neighbors-dropdown", "value"),
    State("start-date-clean2", "data"),
    State("end-date-clean2", "data"),
)
def load_level1_power_curve_subcharts(
    selected_target,
    selected_neighbors,
    start_date,
    end_date,
):
    conn = Databricks_Repository()
    df_power_curve_data = conn.get_wind_power_curves_data(
        start_date=start_date,
        end_date=end_date,
        turbine=selected_target,
    )

    level_1_chart = gen_power_curve_subchart_databricks(df=df_power_curve_data, turbine=selected_target)
    return level_1_chart

@callback(
    Output("peer2peer-chart", "figure"),
    Output("peer-to-peer-table", "data"),
    Input("power-perf-click-store", "data"),
    Input("neighbors-dropdown", "value"),
    State("start-date-clean2", "data"),
    State("end-date-clean2", "data"),
)
def load_level2_power_curve_subcharts(
    selected_target,
    selected_neighbors,
    start_date,
    end_date,
):
    return dash.no_update
    if selected_target in (None, []):
        return dash.no_update

    power_curve_df = load_power_curve_data()
    distribution_df = load_power_distribution_data()
    ws_dist = load_ws_distribution_data()
    surrogation_strategies = load_surrogation_strategies()

    power_curves = power_curve_df.loc[
        power_curve_df.index.get_level_values("Day") != "All"
        ]

    # Filter power curves based on selected date range and average over the days
    mask = (
                   pd.to_datetime(power_curves.index.get_level_values("Day")) >= start_date
           ) & (pd.to_datetime(power_curves.index.get_level_values("Day")) <= end_date)

    filtered_power_curves = power_curves.loc[mask]
    filtered_distribution = distribution_df[mask]

    all_power_curve_counts = {}
    avg_power_curves = {}
    all_r2_values = []
    for neighbor in selected_neighbors:
        r2_value = surrogation_strategies.loc[
            (surrogation_strategies["target"] == selected_target)
            & (surrogation_strategies["surrogate"] == neighbor),
            "bulk_R2",
        ].values[0]
        all_r2_values.append(r2_value)

        # make sure the turbines we need are there if not move to the next
        if (neighbor not in filtered_power_curves.index) or (
                neighbor not in filtered_distribution.index
        ):
            print(
                f"performance.load_level2_power_curve_subcharts: peer turbine {neighbor} not found in power curve or distribution data. Moving to the next turbine"
            )
            selected_neighbors = selected_neighbors.remove(neighbor)
            continue
        # aggregate the power curves by weighting by bin counts
        (
            turbine_power_curve,
            turbine_power_curve_counts,
        ) = calculate_weighted_average_power_by_turbine(
            filtered_power_curves.loc[neighbor], filtered_distribution.loc[neighbor]
        )

        avg_power_curves[neighbor] = turbine_power_curve
        all_power_curve_counts[neighbor] = turbine_power_curve_counts

    (
        turbine_power_curve,
        turbine_power_curve_counts,
    ) = calculate_weighted_average_power_by_turbine(
        filtered_power_curves.loc[selected_target],
        filtered_distribution.loc[selected_target],
    )
    avg_power_curves[selected_target] = turbine_power_curve
    all_power_curve_counts[selected_target] = turbine_power_curve_counts

    turbine_power_curves = pd.concat(avg_power_curves, axis=1).transpose()

    level_2_chart = gen_peer_to_peer_chart(
        selected_neighbors,
        selected_target,
        surrogation_strategies,
        turbine_power_curves,
    )

    TABLE_COLUMNS = ("Pairings", "% AEP Delta")
    TABLE_NULL_VAL = "-"
    table_data = []

    target_power_curve = filtered_power_curves.loc[selected_target].copy()
    target_power_curve_counts = filtered_distribution.loc[selected_target].copy()

    if selected_neighbors is not None:
        for neighbor in selected_neighbors:
            neighbor_power_curve = filtered_power_curves.loc[neighbor]
            neighbor_power_curve_distribution = filtered_distribution.loc[neighbor]

            common_indices = find_common_valid_indices(
                target_power_curve, neighbor_power_curve
            )

            target_aep, ____, ____ = full_calculate_AEP(
                project=selected_target.split("-")[0],
                power_curve=target_power_curve,
                power_curve_distribution=target_power_curve_counts,
                ws_dist=ws_dist,
                valid_indices=common_indices,
            )

            neighbor_aep, ___, ___ = full_calculate_AEP(
                project=selected_target.split("-")[0],
                power_curve=neighbor_power_curve,
                power_curve_distribution=neighbor_power_curve_distribution,
                ws_dist=ws_dist,
                valid_indices=common_indices,
            )
            aep_delta = round(((target_aep - neighbor_aep) / neighbor_aep) * 100, 1)

            row = {
                TABLE_COLUMNS[0]: f"{selected_target} → {neighbor}",
                TABLE_COLUMNS[1]: aep_delta,
            }
            table_data.append(row)

    return level_2_chart, table_data
