"""The App's Landing Page with navigation to its contained Pages."""

from datetime import datetime

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import (
    callback,
    ctx,
    dcc,
    html,
    Input,
    Output,
    State,
    Patch,
)

from Charts.Solar.Tornado import (
    gen_horizontal_bar_chart,
    gen_recovery_chart,
)
from Charts.Solar.DrilledDown import (
    generate_metrics_sparkline,
    generate_all_ws_per_plant_chart,
    generate_ws_time_series,
)
from Charts.Solar.Helpers import (
    extract_plant,
    extract_metric,
    extract_measurement,
    extract_base,
    decide_plants_to_show,
    gen_plant_subtitle,
)
from Charts.Plotters import (
    default_chart,
)
from Model.DataAccess import Databricks_Repository
from Utils.Components import (
    acknowledge_control,
)
from Utils.ISightConstants import (
    METRICS_RADIOITEMS_OPTIONS,
    REVERSE_DATABASE_METRIC_TRANSLATOR,
    INIT_TORNADO_POINTS,
    DATABASE_METRIC_TRANSLATOR,
    TORNADO_CHART_PLOTLY_CONFIG,
    TORNADO_TOOLTIP_CODE_DESCRIPTIONS,
    SOLAR_TOOLTIP_TEXT_LOOKUP,
    SOLAR_TOOLTIP_GRAPHICS_LOOKUP,
    MEASUREMENT_FULLNAME_LOOKUP,
    SOLAR_DRILLED_DOWN_CHART_HEIGHT,
)
from Utils.Transformers import parse_slider_dates

dash.register_page(
    __name__,
    path="/weather-station",
    title="Weather Station Health",
)

def compute_tornado_yaxis_range(chart, limit):
    """Create range property to spotlight top values.

    chart (plotly.Figure): The plotly figure that
        you want to update the range for.
    limit (int): The number of top data points to
        show in the chart. Mind the fact that sorting
        method of the chart is done outside this
        function; therefore, it is possible that the
        undesired points would be shown if the sorting
        done in `gen_horizontal_bar_chart` is problematic.
    """
    if len(chart["data"]) <= 1:
        range_arr = [0, 1]
        return range_arr
    unique_yaxis_vals = set(chart["data"][1]["y"])
    range_arr = [len(unique_yaxis_vals) - limit, len(unique_yaxis_vals)]
    return range_arr

def comma_format(number) -> str:
    """Format a number with commas.

    Args:
        number (int | float): Any number.

    Returns:
        (str): A string with commas separating
            each 3 digits. If the input is
            not a number, a hlepful message
            is returned in its place.
    """
    if not isinstance(number, (int, float)):
        return str(number)
    return f"{number:,}"


def layout():
    clearsky_checkbox = dcc.Checklist(
        id="clear-sky-checkbox",
        options=["Clear Sky"],
        value=[],
        inline=True,
    )
    metric_radioitems = dcc.RadioItems(
        id="tornado-metric",
        options=METRICS_RADIOITEMS_OPTIONS,
        value="pct diff",
        inline=True,
        style={"float": "right"},
    )
    day_night_filter = dcc.RadioItems(
        id="day-night-filter",
        options=["All", "Day", "Night"],
        value="All",
        inline=True,
    )
    min_recov_val = 1
    max_recov_val = 100
    mark_dist = 10
    recovery_slider = dcc.RangeSlider(
        id="recovery-threshold-slider",
        min=min_recov_val,
        max=max_recov_val,
        step=1,
        value=[30, max_recov_val],
        marks={
            val: f"{val}%"
            for val in [1] + list(range(mark_dist, max_recov_val+1, mark_dist))
        },
        tooltip={
            "placement": "top",
            "always_visible": False,
        },
    )

    slider_and_label = html.Div(
        children=[
            html.Label(
                id="recovery-threshold-label",
                htmlFor="recovery-threshold-slider",
                children="Recovery Threshold",
            ),
            recovery_slider,
        ],
    )

    metric_tooltip_images = {}
    for metric in SOLAR_TOOLTIP_TEXT_LOOKUP.keys():
        if metric in SOLAR_TOOLTIP_GRAPHICS_LOOKUP:
            image_container = html.Img(
                className="metric-image-container",
                src=SOLAR_TOOLTIP_GRAPHICS_LOOKUP[metric],
            )
        else:
            image_container = html.Div()
        metric_tooltip_images[metric] = image_container

    tornado_controls_row = dbc.Row(
        # className="g-0",
        align="center",
        justify="center",
        children=[
            dbc.Col(
                children=[
                    metric_radioitems,
                ],
                md=4,
            ),
            dbc.Col(
                children=clearsky_checkbox,
                md=1,
            ),
            dbc.Col(
                children=slider_and_label,
                md=5,
            ),
        ],
    )

    acknowledge_style = {"marginBottom": "0.75rem"}
    metric_tornado_row = dbc.Row(
        # className="g-0",
        align="center",
        justify="between",
        children=[
            dbc.Col(
                children=[
                    acknowledge_control(
                        _id="acknowledged-ghi-solar-weather-stations",
                        label="Acknowledged GHI Stations",
                        placeholder="Select a Weather Station ...",
                        fluid_width="True",
                        style=acknowledge_style,
                    ),
                    html.Span(
                        className="chart-spotlight-control",
                    ),
                    dcc.Graph(
                        id="ghi-chart",
                        className="tornado-chart",
                        figure=default_chart(),
                        clear_on_unhover=True,
                        config=TORNADO_CHART_PLOTLY_CONFIG,
                    ),
                    dcc.Tooltip(
                        id="ghi-graph-tooltip",
                        className="graph-tooltip",
                        background_color="#FCFFA3",
                        direction="left",
                    ),
                ],
                md=4,
            ),
            dbc.Col(
                children=[
                    acknowledge_control(
                        _id="acknowledged-poa-solar-weather-stations",
                        label="Acknowledged POA Stations",
                        placeholder="Select a Weather Station ...",
                        fluid_width="True",
                        style=acknowledge_style,
                    ),
                    html.Span(
                        className="chart-spotlight-control",
                    ),
                    dcc.Graph(
                        id="poa-chart",
                        className="tornado-chart",
                        figure=default_chart(),
                        clear_on_unhover=True,
                        config=TORNADO_CHART_PLOTLY_CONFIG,
                    ),
                    dcc.Tooltip(
                        id="poa-graph-tooltip",
                        className="graph-tooltip",
                        background_color="#FCFFA3",
                        direction="left",
                    ),
                ],
                md=4,
            ),
            dbc.Col(
                children=[
                    acknowledge_control(
                        _id="acknowledged-bom-solar-weather-stations",
                        label="Acknowledged BOM Stations",
                        placeholder="Select a Weather Station ...",
                        fluid_width="True",
                        style=acknowledge_style,
                    ),
                    html.Span(
                        className="chart-spotlight-control",
                        children=[
                            day_night_filter,
                        ]
                    ),
                    dcc.Graph(
                        id="bom-chart",
                        className="tornado-chart",
                        figure=default_chart(),
                        clear_on_unhover=True,
                        config=TORNADO_CHART_PLOTLY_CONFIG,
                    ),
                    dcc.Tooltip(
                        id="bom-graph-tooltip",
                        className="graph-tooltip",
                        background_color="#FCFFA3",
                        direction="left",
                    ),
                ],
                md=4,
            ),
        ],
    )

    drilled_down_charts_card = html.Div(
        id="drilled-down-charts-container",
        children=[
            dcc.Tabs(id="tabs-styled-with-inline", value='tab-1', children=[
                dcc.Tab(
                    label="All Metrics",
                    value="tab-1",
                    children=[
                        dcc.Graph(
                            id="clicked-weather-station-metrics",
                            style={"height": f"{SOLAR_DRILLED_DOWN_CHART_HEIGHT}px"},
                            config={"responsive": True},
                        ),
                    ],
                ),
                dcc.Tab(
                    label="All Weather Stations in Plant",
                    value="tab-2",
                    children=[
                        dcc.Graph(
                            id="clicked-all-weather-stations-per-plant",
                            style={"height": f"{SOLAR_DRILLED_DOWN_CHART_HEIGHT}px"},
                            config={"responsive": True},
                        ),
                    ],
                ),
                dcc.Tab(
                    label="10-Min Time Series",
                    value="tab-3",
                    children=[
                        dcc.Graph(
                            id="clicked-time-series-weather-station",
                            style={"height": f"{SOLAR_DRILLED_DOWN_CHART_HEIGHT}px"},
                            config={"responsive": True},
                        ),
                        html.P(
                            id="last-updated-callout-10min-time-series",
                            className="last-updated-callout",
                            style={"margin": 0},
                        ),
                    ],
                ),
            ]),
        ]
    )

    metrics_info_btn = dbc.Button(
        id="open-metrics-modal",
        className="metrics-details-button",
        children=[
            html.Span([
                html.I(id="metrics-info-icon", className="bi bi-journal-bookmark me-2"),
                html.Span("About our Metrics"),
            ])
        ],
        n_clicks=0,
    )

    close_metrics_modal_btn = dbc.Button(
        id="close-metrics-modal",
        className="close-metrics-modal",
        children=[
            html.Span([
                html.I(id="metrics-info-icon", className="bi bi-x"),
            ])
        ],
        n_clicks=0,
    )

    modal_tab_content = dcc.Tabs(
        [
            dcc.Tab(
                label=metric.title(),
                children=[
                    dcc.Markdown(
                        className="metric-description",
                        children=SOLAR_TOOLTIP_TEXT_LOOKUP[metric],
                        mathjax=True,
                        highlight_config=dict(theme="dark"),
                    ),
                    metric_tooltip_images[metric],
                ],
            )
            for metric in SOLAR_TOOLTIP_TEXT_LOOKUP.keys()
        ],
    )
    modal_metrics = dbc.Modal(
        id="modal-metrics",
        children=[
            html.H1("The Weather Station Metrics"),
            html.P("(To exit this view, press the X or ESC on your keyboard.)", className="secondary-text"),
            modal_tab_content,
            close_metrics_modal_btn,
        ],
        scrollable=True,
        centered=True,
        is_open=False,
    )

    download_recovery_btn = dbc.Button(
        id="download-recovery-chart-button",
        className="metrics-details-button",
        children=[
            html.Span([
                html.I(id="recovery-btn-icon", className="bi bi-download me-2"),
                html.Span("Download Recovery Data"),
            ])
        ],
        n_clicks=0,
    )

    HEADER_STYLE = {
        "fontWeight": 400,
        "color": "#FFF",
        "margin": 0,
        "textAlign": "center",
        "marginBottom": "0.5rem"
    }
    CARD_STYLE = {
        "borderRadius": "2px",
        "border": "2px solid #FFF",
        "marginBottom": "2rem",
        "marginTop": "2rem",
        "marginLeft": "4rem",
        "marginRight": "4rem",
        "paddingLeft": "1rem",
        "paddingRight": "1rem",
    }
    return dbc.Container(
        fluid=True,
        class_name="wrap",
        children=[
            dcc.Download(id="download-comparison-table-container"),
            dcc.Download(id="download-recovery-chart-data"),
            html.Div(
                className="card",
                style=CARD_STYLE,
                children=[
                    html.H2(
                        id="metric-tornado-title",
                        children="Metric Comparison Between Stations",
                        style=HEADER_STYLE,
                    ),
                    metrics_info_btn,
                    modal_metrics,

                    tornado_controls_row,
                    metric_tornado_row,
                    html.P(
                        id="last-updated-callout-tornado-charts",
                        className="last-updated-callout",
                    ),
                    drilled_down_charts_card,
                ],
            ),
            html.Div(
                className="card",
                style=CARD_STYLE,
                children=[
                    html.H2(
                        id="recovery-tornado-title",
                        children="Weather Stations by Recovery",
                        style=HEADER_STYLE,
                    ),
                    download_recovery_btn,
                    dbc.Row(
                        className="g-0",
                        align="center",
                        justify="evenly",
                        children=[
                            dbc.Col(
                                children=[
                                    dcc.Graph(
                                        id="recoveries-chart",
                                        figure=default_chart(),
                                    ),
                                ],
                                md=12,
                            ),
                        ],
                    ),
                    html.P(
                        id="last-updated-callout-recovery-chart",
                        className="last-updated-callout",
                    ),
                ],
            ),
        ],
    )


@callback(
    Output("last-updated-callout-tornado-charts", "children"),
    Input("url", "pathname"),
)
def update_tornados_last_updated_callout(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.metrics"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the Tornado Charts was Last Updated on {last_updated}."

@callback(
    Output("last-updated-callout-10min-time-series", "children"),
    Input("url", "pathname"),
    prevent_inital_callback=True,
)
def update_10min_time_series_last_updated_callout(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.weather_station_time_series"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the 10-Min Time Series was Last Updated on {last_updated}."

@callback(
    Output("last-updated-callout-recovery-chart", "children"),
    Input("url", "pathname"),
)
def update_recovery_chart_last_updated_callout(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.recovery"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the Recovery Chart was Last Updated on {last_updated}."

@callback(
    Output("download-recovery-chart-data", "data"),
    Input("download-recovery-chart-button", "n_clicks"),
    State("recoveries-chart", "figure"),
    State("recovery-tornado-title", "children"),
    prevent_initial_callback=True,
)
def download_recovery_chart_data(n, figure, recovery_title):
    if not n:
        return dash.no_update

    recovery_arr = figure["data"][0]["x"]
    name_arr = figure["data"][0]["y"]
    df = pd.DataFrame({
        "Metric Attributes": name_arr,
        "Recovery": recovery_arr,
    })

    title = f"{recovery_title}.csv"
    return dcc.send_data_frame(df.to_csv, title)

@callback(
    Output("modal-metrics", "is_open"),
    Input("open-metrics-modal", "n_clicks"),
    Input("close-metrics-modal", "n_clicks"),
    State("modal-metrics", "is_open"),
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

@callback(
    Output("acknowledged-ghi-solar-weather-stations", "options"),
    Output("acknowledged-poa-solar-weather-stations", "options"),
    Output("acknowledged-bom-solar-weather-stations", "options"),
    Input("url", "pathname"),
)
def populate_ghi_acknowledge_control_options(pathname):
    conn = Databricks_Repository()
    options = conn.get_plant_weatherstation_pairs()
    return options, options, options


@callback(
    Output("clicked-weather-station-metrics", "figure"),
    Output("clicked-all-weather-stations-per-plant", "figure"),
    Output("clicked-time-series-weather-station", "figure"),
    Output("drilled-down-charts-container", "className"),
    Input("ghi-chart", "clickData"),
    Input("poa-chart", "clickData"),
    Input("bom-chart", "clickData"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("tornado-metric", "value"),
    Input("recovery-threshold-slider", "value"),
    Input("project-dropdown", "value"),
    Input("clear-sky-checkbox", "value"),
    State("date-intervals-store", "data"),
    prevent_inital_call=True,
)
def update_drilled_down_card_and_charts(
    ghiClickData,
    poaClickData,
    bomClickData,
    picker_start_date,
    picker_end_date,
    metric,
    recovery,
    project_dropdown,
    clear_sky_checkbox,
    date_intervals_store,
):
    if (
        ctx.triggered_id in (
            "date-picker-range",
            "tornado-metric",
            "recovery-threshold-slider",
            "project-dropdown",
            "clear-sky-checkbox",
        )
        or (
                ghiClickData is None
            and poaClickData is None
            and bomClickData is None
        )
    ):
        output_chart = default_chart()
        output_chart.update_layout(height=SOLAR_DRILLED_DOWN_CHART_HEIGHT)
        output_chart.update_layout(clickmode="none", dragmode=False)
        return output_chart, output_chart, output_chart, "disabled-container"

    clickData = None
    if ctx.triggered_id == "ghi-chart":
        clickData = ghiClickData
    elif ctx.triggered_id == "poa-chart":
        clickData = poaClickData
    elif ctx.triggered_id == "bom-chart":
        clickData = bomClickData
    if clickData is None:
        return dash.no_update

    dt_start_date = datetime.fromisoformat(picker_start_date)
    dt_end_date = datetime.fromisoformat(picker_end_date)

    tag = clickData["points"][0]["customdata"][0]
    weather_station = tag.split("_")[0]
    conn = Databricks_Repository()

    # create the subchart with all metrics for clicked weather station
    df = conn.get_daily_values_for_weather_station(
        weather_station=weather_station,
        start_date=dt_start_date,
        end_date=dt_end_date,
    )

    clear_sky_df = conn.get_clear_sky(
        start_date=dt_start_date,
        end_date=dt_end_date,
    )

       
    plant_label = extract_plant(tag)
    clear_sky_df = clear_sky_df[clear_sky_df["plant"] == plant_label]
    all_metrics_subchart = generate_metrics_sparkline(
        df=df,
        clear_sky_df=clear_sky_df,
        tag=tag,
        start_date=dt_start_date,
        end_date=dt_end_date,
    )

    metric_label = REVERSE_DATABASE_METRIC_TRANSLATOR[extract_metric(tag)]
    meas_label = extract_measurement(tag)
    ws_per_plant_df = conn.get_metrics_data(
        start_date=dt_start_date,
        end_date=dt_end_date,
        plant=plant_label,
        measurement=meas_label,
        metric=metric_label,
        should_aggregate=False,
    )
    all_stations_subchart = generate_all_ws_per_plant_chart(
        df=ws_per_plant_df,
        tag=tag,
        start_date=dt_start_date,
        end_date=dt_end_date,
    )

    df_time_series = conn.get_weather_station_time_series(
        plant=plant_label,
        measurement=meas_label,
        start_date=dt_start_date,
        end_date=dt_end_date,
    )
    time_series_subchart = generate_ws_time_series(
        tag=tag,
        df=df_time_series,
    )

    return (
        all_metrics_subchart,
        all_stations_subchart,
        time_series_subchart,
        "not-disabled-container",
    )

def update_tooltip_content(hoverData, show_table=False, with_direction=None, show_clear_sky=None):
    """Helper callback function for managing the tornado tooltip state.

    Since there are multiple tooltips to manage, each with their own
    particularities, it makes sense to create this helper function.

    Args:
        hoverData (dict): This comes from the hoverData property of
            'poa-chart', 'bom-chart', or the 'ghi-chart' component ID.
        update_tooltip_content (bool): This determines if we display a
            table with metrics / info to display in the tooltip.
        with_direction (bool): This param decides if an additional
            property is returned by this function: the `direction`
            property.
        show_clear_sky (bool): This param decides if the percentage of
            clear sky days is displayed in the tooltip.
            
            Note that there is a possibility that if the Clear Sky control
            is turned on (eg. checkbox is checked) in the UI, then if this
            param is True, the metric number might not be correct.

    Returns:
        (tuple): If `with_direction` is true, this function
            returns a 3 tuple:
            - (show, bbox, children)
            Otherwise, a 4 tuple:
            - (show, bbox, children, direction)

            Where show, bbox, children, direction are available component
            properties of dcc.Tooltips.
    """
    if with_direction is None:
        with_direction = False
    if show_clear_sky is None:
        show_clear_sky = False
    if hoverData is None or "customdata" not in hoverData["points"][0]:
        if with_direction:
            return False, dash.no_update, dash.no_update, dash.no_update
        return False, dash.no_update, dash.no_update

    # We should only hit this condition for the left-most tornado
    direction = "left"

    # 230 is roughly the length of the tooltip in pixels
    if hoverData["points"][0]["bbox"]["x0"] < 230:
        direction = "right"

    pt = hoverData["points"][0]
    bbox = pt["bbox"]

    tag = pt["customdata"][0]
    # remove metric from tag since redundant
    tag = tag.split("_", maxsplit=1)[0]

    metric_order = list(DATABASE_METRIC_TRANSLATOR.keys())

    e = pt["customdata"][ metric_order.index("euclidean") + 1 ]
    j = pt["customdata"][ metric_order.index("jensen-shanon") + 1 ]
    m = pt["customdata"][ metric_order.index("manhattan") + 1 ]
    c = pt["customdata"][ metric_order.index("cosine") + 1 ]
    pct_diff = pt["customdata"][ metric_order.index("pct diff") + 1 ]
    lost_energy = pt["customdata"][ len(metric_order) + 1 ]
    recovery = pt["customdata"][ len(metric_order) + 2 ]
    clear_sky = pt["customdata"][ len(metric_order) + 3 ]
    lost_revenue = pt["customdata"][ len(metric_order) + 4 ]

    # add comma formatting to numbers
    e = comma_format(e)
    m = comma_format(m)
    recovery = comma_format(recovery)
    lost_energy = comma_format(lost_energy)
    lost_revenue = comma_format(lost_revenue)

    table = f"""
    | E    | M    | J    | C    | Lost MWh       | Lost $         |
    | :--: | :--: | :--: | :--: | :--:           | :--:           |
    | {e}  | {m}  | {j}  | {c}  | {lost_energy}  | {lost_revenue} |
    """

    children = [
        html.B(tag),
        html.P(f"SolarAnywhere Deviation (%): {pct_diff}"),
        html.P(f"Recovery (%): {recovery}"),
    ]
    if show_clear_sky:
        # convert ratio to percentages
        a, b = clear_sky.split("/")
        a = int(a)
        b = int(b)
        clear_sky_pct = round(a / b * 100, 2)
        clear_sky_tooltip_line = html.P(f"Clear Sky (%): {clear_sky_pct} [{clear_sky} days are clear sky]")
        children.append(clear_sky_tooltip_line)

    if show_table:
        children.extend([
            dcc.Markdown(table, mathjax=True),
        ])
        disclaimer_text = ""
        for idx, code in enumerate(TORNADO_TOOLTIP_CODE_DESCRIPTIONS.keys()):
            if idx != len(TORNADO_TOOLTIP_CODE_DESCRIPTIONS) - 1:
                line_ending = "\n\n"
            disclaimer_text += f"({TORNADO_TOOLTIP_CODE_DESCRIPTIONS[code]}){line_ending}"
        children.append(dcc.Markdown(disclaimer_text, mathjax=False))

    if with_direction:
        return True, bbox, children, direction
    return True, bbox, children

@callback(
    Output("bom-graph-tooltip", "show"),
    Output("bom-graph-tooltip", "bbox"),
    Output("bom-graph-tooltip", "children"),
    Input("bom-chart", "hoverData"),
)
def update_bom_chart_tooltip(hoverData, show_table=True):
    return update_tooltip_content(
        hoverData,
        show_table=show_table,
        show_clear_sky=True,
    )

@callback(
    Output("poa-graph-tooltip", "show"),
    Output("poa-graph-tooltip", "bbox"),
    Output("poa-graph-tooltip", "children"),
    Input("poa-chart", "hoverData"),
)
def update_poa_chart_tooltip(hoverData, show_table=True):
    return update_tooltip_content(
        hoverData,
        show_table=show_table,
        show_clear_sky=True,
    )

@callback(
    Output("ghi-graph-tooltip", "show"),
    Output("ghi-graph-tooltip", "bbox"),
    Output("ghi-graph-tooltip", "children"),
    Output("ghi-graph-tooltip", "direction"),
    Input("ghi-chart", "hoverData"),
    prevent_initial_call=True,
)
def update_ghi_chart_tooltip(hoverData, show_table=True):
    return update_tooltip_content(
        hoverData,
        show_table=show_table,
        with_direction=True,
        show_clear_sky=True,
    )

@callback(
    Output("metric-tornado-title", "children"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("tornado-metric", "value"),
    Input("recovery-threshold-slider", "value"),
    Input("project-dropdown", "value"),
    Input("self-perform-checkbox", "value"),
    Input("clear-sky-checkbox", "value"),
    State("date-intervals-store", "data"),
)
def update_tornado_section_title(
    picker_start_date,
    picker_end_date,
    tornado_metric,
    recovery_values,
    plant_filter,
    self_perform_checkbox,
    clear_sky_checkbox,
    date_intervals_store,
):
    dt_start_date = datetime.fromisoformat(picker_start_date)
    dt_end_date = datetime.fromisoformat(picker_end_date)
    conn = Databricks_Repository()
    plant_arr = decide_plants_to_show(
        conn=conn,
        self_perform_checkbox=self_perform_checkbox, 
        plant_filter=plant_filter,
    )
    substring_plant = gen_plant_subtitle(plant_arr)
    substring_recov = f", {recovery_values[0]}% ≤  Recovery ≤  {recovery_values[1]}%"
    substring_clearsky = ", Clear Sky Days" if clear_sky_checkbox == ["Clear Sky"] else ""

    title_start = dt_start_date.strftime("%m/%d")
    title_end = dt_end_date.strftime("%m/%d")
    return f"{tornado_metric.title()} Comparison Across {substring_plant}{substring_recov}{substring_clearsky} ({title_start} to {title_end})"


def create_tornado_chart(
    conn,
    dt_start_date,
    dt_end_date,
    plant,
    measurement,
    recovery_df,
    metric,
    recovery_values,
    only_clear_sky_days,
    acknowledged_stations,
    day_night_filter=None,
    base_color=None,
):
    """Create a tornado chart for the Weather Station Page.
    
    Args:
        ...
    Return:
        ...
    """
    budget_deviation_df = conn.get_budget_deviation(
        start_date=dt_start_date,
        end_date=dt_end_date,
        measurement=measurement,
        kpi="energy",
    )
    all_clear_sky_ratios_df = conn.get_all_clear_sky_ratios(
        start_date=dt_start_date,
        end_date=dt_end_date,
    )
    lost_revenue_df = conn.get_budget_deviation(
        start_date=dt_start_date,
        end_date=dt_end_date,
        measurement=measurement,
        kpi="revenue",
    )

    # fetch the metrics data just for the given tornado
    metrics_df = conn.get_metrics_data(
        metric = None,
        measurement = measurement,
        start_date = dt_start_date,
        end_date = dt_end_date,
        plant = plant,
        should_aggregate = True,
        only_clear_sky_days=only_clear_sky_days,
        day_night_filter=day_night_filter,
    )

    # remove all acknowledged weather stations
    weather_stations_to_remove = acknowledged_stations
    filtered_columns = [
        col for col in metrics_df.columns
        if col != "date" and '-' in col and any(
            col.split('-')[0] == crit.split('-')[0] and col.split('-')[3] == crit.split('-')[1]
            for crit in weather_stations_to_remove
        )
    ]
    sorted_metrics_df = metrics_df.drop(columns=filtered_columns)

    sorted_metrics_df = sorted_metrics_df.iloc[0].sort_values(na_position="first")
    chart = gen_horizontal_bar_chart(
        data=sorted_metrics_df,
        recovery_df=recovery_df,
        metric=metric,
        color_by_pct_diff=True,
        budget_deviation_df=budget_deviation_df,
        lost_revenue_df=lost_revenue_df,
        all_clear_sky_ratios_df=all_clear_sky_ratios_df,
        only_clear_sky_days=only_clear_sky_days,
        base_color=base_color,
    )

    # construct the tornado title showing context
    main_title = f"{MEASUREMENT_FULLNAME_LOOKUP[measurement]} [{measurement}]"

    if len(chart["data"]) <= 1:
        ws_count = 0
    else:
        ws_count = len(chart["data"][1]["y"])
    suffix = "s" if ws_count != 1 else ""
    ws_subtitle = f"{ws_count} Weather Station{suffix}"
    recov_subtitle = f"{recovery_values[0]}% ≤ Recovery ≤ {recovery_values[1]}%"
    title = f"<b>{main_title}</b><br>({ws_subtitle}, {recov_subtitle})"

    chart.update_layout(
        title=title,
        height=600,
        # Note that height and margin values need to be mirrored in the CSS stylesheet
        margin=dict(
            l=100,
            t=90,
            b=120,
            autoexpand=False,
        ),
        xaxis=dict(showline=True),
        yaxis=dict(showline=True),
    )
    # auto-focus on the top datapoints
    yaxis_range = compute_tornado_yaxis_range(chart=chart, limit=INIT_TORNADO_POINTS)
    chart.update_layout(yaxis=dict(range=yaxis_range))
    return chart


def update_tornado_callback(
    picker_start_date,
    picker_end_date,
    metric,
    recovery_values,
    plant_filter,
    self_perform_checkbox,
    clear_sky_checkbox,
    acknowledged_stations,
    date_intervals_store,
    day_night_filter,
    measurement,
    base_color,
):
    """A reusable callback function that are behind all tornado charts."""

    dt_start_date = datetime.fromisoformat(picker_start_date)
    dt_end_date = datetime.fromisoformat(picker_end_date)
    conn = Databricks_Repository()
    plant_arr = decide_plants_to_show(
        conn=conn,
        self_perform_checkbox=self_perform_checkbox,
        plant_filter=plant_filter,
    )

    if clear_sky_checkbox == ["Clear Sky"]:
        only_clear_sky_days = True
    else:
        only_clear_sky_days = False

    recovery_df = conn.get_recovery_data(
        start_date = dt_start_date,
        end_date = dt_end_date,
        plant = plant_arr,
        aggr_func = "avg",
        day_night_filter=day_night_filter,
    )
    recovery_df = recovery_df.iloc[0].sort_values(ascending=False)

    # filter out recoveries we don't want to see in the charts
    recovery_df = recovery_df[recovery_df <= recovery_values[1]]
    recovery_df = recovery_df[recovery_df >= recovery_values[0]]

    # remove "_recovery" from the ends of the column names
    recovery_df.rename(lambda x: x.split("_")[0], inplace=True)

    recovery_df = recovery_df.loc[~recovery_df.index.duplicated()]

    chart = create_tornado_chart(
        conn=conn,
        dt_start_date=dt_start_date,
        dt_end_date=dt_end_date,
        plant=plant_arr,
        measurement=measurement,
        recovery_df=recovery_df,
        metric=metric,
        recovery_values=recovery_values,
        only_clear_sky_days=only_clear_sky_days,
        acknowledged_stations=acknowledged_stations,
        day_night_filter=day_night_filter,
        base_color=base_color,
    )
    return chart

@callback(
    Output("ghi-chart", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("tornado-metric", "value"),
    Input("recovery-threshold-slider", "value"),
    Input("project-dropdown", "value"),
    Input("self-perform-checkbox", "value"),
    Input("clear-sky-checkbox", "value"),
    Input("acknowledged-ghi-solar-weather-stations", "value"),
    State("date-intervals-store", "data"),
)
def update_ghi_tornado(
    picker_start_date,
    picker_end_date,
    metric,
    recovery_values,
    plant_filter,
    self_perform_checkbox,
    clear_sky_checkbox,
    acknowledged_stations,
    date_intervals_store,
    day_night_filter="All",
    measurement="GHI",
):
    base_color = "#02BCF0"
    return update_tornado_callback(
        picker_start_date=picker_start_date,
        picker_end_date=picker_end_date,
        metric=metric,
        recovery_values=recovery_values,
        plant_filter=plant_filter,
        self_perform_checkbox=self_perform_checkbox,
        clear_sky_checkbox=clear_sky_checkbox,
        acknowledged_stations=acknowledged_stations,
        date_intervals_store=date_intervals_store,
        day_night_filter=day_night_filter,
        measurement=measurement,
        base_color=base_color,
    )

@callback(
    Output("poa-chart", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("tornado-metric", "value"),
    Input("recovery-threshold-slider", "value"),
    Input("project-dropdown", "value"),
    Input("self-perform-checkbox", "value"),
    Input("clear-sky-checkbox", "value"),
    Input("acknowledged-poa-solar-weather-stations", "value"),
    State("date-intervals-store", "data"),
)
def update_poa_tornado(
    picker_start_date,
    picker_end_date,
    metric,
    recovery_values,
    plant_filter,
    self_perform_checkbox,
    clear_sky_checkbox,
    acknowledged_stations,
    date_intervals_store,
    day_night_filter="All",
    measurement="POA",
):
    base_color = "#02BCF0"
    return update_tornado_callback(
        picker_start_date=picker_start_date,
        picker_end_date=picker_end_date,
        metric=metric,
        recovery_values=recovery_values,
        plant_filter=plant_filter,
        self_perform_checkbox=self_perform_checkbox,
        clear_sky_checkbox=clear_sky_checkbox,
        acknowledged_stations=acknowledged_stations,
        date_intervals_store=date_intervals_store,
        day_night_filter=day_night_filter,
        measurement=measurement,
        base_color=base_color,
    )

@callback(
    Output("bom-chart", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("tornado-metric", "value"),
    Input("recovery-threshold-slider", "value"),
    Input("project-dropdown", "value"),
    Input("self-perform-checkbox", "value"),
    Input("clear-sky-checkbox", "value"),
    Input("acknowledged-bom-solar-weather-stations", "value"),
    Input("day-night-filter", "value"),
    State("date-intervals-store", "data"),
)
def update_bom_tornado(
    picker_start_date,
    picker_end_date,
    metric,
    recovery_values,
    plant_filter,
    self_perform_checkbox,
    clear_sky_checkbox,
    acknowledged_stations,
    day_night_filter,
    date_intervals_store,
    measurement="BOM",
):
    base_color = "#02BCF0"
    return update_tornado_callback(
        picker_start_date=picker_start_date,
        picker_end_date=picker_end_date,
        metric=metric,
        recovery_values=recovery_values,
        plant_filter=plant_filter,
        self_perform_checkbox=self_perform_checkbox,
        clear_sky_checkbox=clear_sky_checkbox,
        acknowledged_stations=acknowledged_stations,
        date_intervals_store=date_intervals_store,
        day_night_filter=day_night_filter,
        measurement=measurement,
        base_color=base_color,
    )


@callback(
    Output("recoveries-chart", "figure"),
    Output("recovery-tornado-title", "children"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("project-dropdown", "value"),
    Input("self-perform-checkbox", "value"),
    State("date-intervals-store", "data"),
)
def populate_recovery_chart_and_title(
    picker_start_date,
    picker_end_date,
    plant_filter,
    self_perform_checkbox,
    date_intervals_store,
):
    dt_start_date = datetime.fromisoformat(picker_start_date)
    dt_end_date = datetime.fromisoformat(picker_end_date)

    conn = Databricks_Repository()
    plant_arr = decide_plants_to_show(
        conn=conn,
        self_perform_checkbox=self_perform_checkbox,
        plant_filter=plant_filter,
    )
    recovery_df = conn.get_recovery_data(
        start_date = dt_start_date,
        end_date = dt_end_date,
        plant = plant_arr,
        aggr_func = "avg",
    )

    recovery_df = recovery_df.iloc[0].sort_values(ascending=False)

    # Make sure that we are dropping duplicate recoveries
    recovery_df = recovery_df.groupby(recovery_df.index.map(extract_base)).first()
    recovery_df = recovery_df.sort_values(ascending=False)

    chart = gen_recovery_chart(
        data=recovery_df,
    )

    # construct title
    substring_plant = gen_plant_subtitle(plant_arr)
    title_start = dt_start_date.strftime("%m/%d")
    title_end = dt_end_date.strftime("%m/%d")
    title = (
        f"Weather Station Recovery Across {substring_plant} ({title_start} to {title_end})"
    )
    return chart, title

@callback(
    Output("recovery-threshold-label", "children"),
    Input("recovery-threshold-slider", "value"),
)
def update_recovery_threshold_label_text(value):
    return f"{value[0]}% ≤ Recovery ≤ {value[1]}%"

@callback(
    Output("ghi-chart", "figure", allow_duplicate=True),
    Output("poa-chart", "figure", allow_duplicate=True),
    Output("bom-chart", "figure", allow_duplicate=True),
    Input("ghi-chart", "clickData"),
    Input("poa-chart", "clickData"),
    Input("bom-chart", "clickData"),
    State("ghi-chart", "figure"),
    State("poa-chart", "figure"),
    State("bom-chart", "figure"),
    prevent_initial_call=True,
)
def highlight_weather_stations_in_same_plant(
    ghiClickData,
    poaClickData,
    bomClickData,
    last_ghi_fig,
    last_poa_fig,
    last_bom_fig,
):
    if ghiClickData is None and poaClickData is None and bomClickData is None:
        return dash.no_update

    patched_fig = Patch()
    patched_poa_fig = Patch()
    patched_bom_fig = Patch()

    if ctx.triggered_id == "ghi-chart":
        triggeredClickData = ghiClickData
    elif ctx.triggered_id == "poa-chart":
        triggeredClickData = poaClickData
    elif ctx.triggered_id == "bom-chart":
        triggeredClickData = bomClickData

    # figure out what plant you clicked
    if "customdata" in triggeredClickData["points"][0]:
        clicked_tag = triggeredClickData["points"][0]["customdata"][0]
        clicked_plant = extract_plant(clicked_tag)
    else:
        y_val = triggeredClickData["points"][0]["y"]
        clicked_plant = y_val.split("-")[0]

    # highlight traces across tornado charts sharing the same plant

    # GHI Tornado
    BIG_MARKER_SIZE = 14
    DEFAULT_MARKER_SIZE = 6
    for idx, y in enumerate(last_ghi_fig["data"][1]["y"]):
        if y.startswith(clicked_plant):
            patched_fig["data"][1]["marker"]["size"][idx] = BIG_MARKER_SIZE
        else:
            patched_fig["data"][1]["marker"]["size"][idx] = DEFAULT_MARKER_SIZE

    # POA Tornado
    for idx, y in enumerate(last_poa_fig["data"][1]["y"]):
        if y.startswith(clicked_plant):
            patched_poa_fig["data"][1]["marker"]["size"][idx] = BIG_MARKER_SIZE
        else:
            patched_poa_fig["data"][1]["marker"]["size"][idx] = DEFAULT_MARKER_SIZE

    # BOM Tornado
    for idx, y in enumerate(last_bom_fig["data"][1]["y"]):
        if y.startswith(clicked_plant):
            patched_bom_fig["data"][1]["marker"]["size"][idx] = BIG_MARKER_SIZE
        else:
            patched_bom_fig["data"][1]["marker"]["size"][idx] = DEFAULT_MARKER_SIZE

    return patched_fig, patched_poa_fig, patched_bom_fig
