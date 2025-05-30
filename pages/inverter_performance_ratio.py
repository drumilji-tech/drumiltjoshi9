"""The Inverter Performance Page."""

from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import ctx, dcc, html, callback, Input, Output, State

from Charts.Plotters import default_chart
from Charts.Solar.Helpers import (
    extract_plant,
    decide_plants_to_show,
    gen_plant_subtitle,
)
from Charts.Solar.Inverters import (
    gen_inverters_treemap,
    gen_inverters_number_line,
    gen_level1_subchart,
    gen_level2_subchart,
    gen_level3_subchart,
    gen_level4_subchart,
)
from Model.DataAccess import Databricks_Repository
from Utils.Components import (
    acknowledge_control,
)
from Utils.UiConstants import (
    PERFORMANCE_METRICS,
    DEFAULT_CHART_HEIGHT,
    POWER_PERFORMANCE_TREEMAP_OPTIONS,
)
from Utils.ISightConstants import SOLAR_DRILLED_DOWN_CHART_HEIGHT
from Utils.Transformers import parse_slider_dates

TOOLTIP_DELAY_TIMINGS = {
    "show": 600,
    "hide": 750,
}
SOLAR_TREEMAP_TOOLTIP_TEXT_LOOKUP = {
    PERFORMANCE_METRICS[0]: (
        "The amount of money lost or gained relative to what was expected "
        "from the inverter over the selected period of time."
    ),
    PERFORMANCE_METRICS[1]: (
        "The amount of energy, in MWh, that is not generated relative to "
        "what was expected from the turbine over the selected period of "
        "time.",
    ),
    PERFORMANCE_METRICS[2]: (
        "A measurement of the deviation in performance relative to the rest "
        "of the inverters.",
    ),
}

dash.register_page(
    __name__,
    path="/inverter-performance",
    title="Inverter Performance",
)


def gen_popover_component(label, contents, style=None, placement=None):
    """Generate a labelled button that houses content.
    
    Args:
        label (str): The displayed label on the button.
        contents (list): The children of the dbc.Popover
            component. You can put anything in here,
            including something as simple as a string,
            to be displayed upon clicking the button.
        style (dict, Optional): A style for the button.
        placement (str, Optional): Determines the direction
            the popover will appear out from the button.

    Returns:
        popover (html.Div): The popover component.
    """
    if style is None:
        style = {}
    if placement is None:
        placement = "left-start"
    popover = html.Div(
        children=[
            dbc.Button(
                className="popover-button",
                style=style,
                children=[
                    html.Span([
                        html.I(id="info-icon", className="bi bi-info-circle-fill me-2"),
                        html.Span(label),
                    ])
                ],
                id="component-target-inv-perf",
                n_clicks=0,
            ),
            dbc.Popover(
                children=contents,
                body=True,
                target="component-target-inv-perf",
                trigger="click",
                flip=False,
                placement=placement,
            ),
        ],
    )
    return popover

def layout():
    treemap_graph = dcc.Graph(
        id="inverters-treemap",
        className="treemap",
        figure=default_chart(),
    )

    inverters_numberline_graph = dcc.Graph(
        id="inverters-performance-number-line",
        figure=default_chart(),
    )

    label = "About Relative Deviation"
    popover_contents = dcc.Markdown('''
The **Relative Deviation** of an inverter is a measure that describes the relationship between its active power and the average active power of top performing inverters across the fleet.
  - It is normalized to account for differences in installed DC capacity.

More precisely, it represents the daily sum of 6-hour rolling sums of 10-minute Z-Scores, where:
  - A 10-minute Z-score of +N means an Inverter's `ActivePowerNormalized` is N standard deviations above the `ActivePowerNormalizedAvg`.
  - A 10-minute Z-score of -N means an Inverter's `ActivePowerNormalized` is N standard deviations below the `ActivePowerNormalizedAvg`.

(NB the decision to use a 6-hour rolling window was to help filter out transient fluctuations.)
    ''', mathjax=True)
    popover = gen_popover_component(
        label=label,
        contents=popover_contents,
        style=None,
        placement="right-end",
    )
    treemap_and_subcharts = html.Div(
        id="treemap-heatmap-box4",
        className="treemap-subcharts-container",
        children=[
            treemap_graph,
            inverters_numberline_graph,
            popover,
            html.Div(
                id="heatmap-box4",
                className="is-closed",
                children=[
                    dcc.Tabs(
                        id="heatmap-toggle4",
                        className="heatmap-toggle",
                        value="level-1",
                        children=[
                            dcc.Tab(
                                label="Irradiance-Capacity Regression",
                                value="level-1",
                                children=[
                                    dcc.Graph(
                                        id="solar-inverters-level1-subplot",
                                        figure=default_chart("#171717"),
                                        style={"height": f"{SOLAR_DRILLED_DOWN_CHART_HEIGHT}px"},
                                        config={"responsive": True},
                                    ),
                                    html.P(
                                        id="last-updated-callout-inverters-level1-subplot",
                                        className="last-updated-callout",
                                        style={"margin": 0},
                                    ),
                                ],
                            ),
                            dcc.Tab(
                                label="Correlation Plot",
                                value="level-2",
                                children=[
                                    dcc.Graph(
                                        id="solar-inverters-level2-subplot",
                                        figure=default_chart("#171717"),
                                        style={"height": f"{SOLAR_DRILLED_DOWN_CHART_HEIGHT}px"},
                                        config={"responsive": True},
                                    ),
                                    html.P(
                                        id="last-updated-callout-inverters-level2-subplot",
                                        className="last-updated-callout",
                                        style={"margin": 0},
                                    ),
                                ],
                            ),
                            dcc.Tab(
                                label="Inverter's Deviation from Plant",
                                value="level-3",
                                children=[
                                    dcc.Graph(
                                        id="solar-inverters-level3-subplot",
                                        figure=default_chart("#171717"),
                                        style={"height": f"{SOLAR_DRILLED_DOWN_CHART_HEIGHT}px"},
                                        config={"responsive": True},
                                    ),
                                    html.P(
                                        id="last-updated-callout-inverters-level3-subplot",
                                        className="last-updated-callout",
                                        style={"margin": 0},
                                    ),
                                ],
                            ),
                            dcc.Tab(
                                label="10-Min Time Series",
                                value="level-4",
                                children=[
                                    dcc.Graph(
                                        id="solar-inverters-level4-subplot",
                                        figure=default_chart("#171717"),
                                        style={"height": f"{SOLAR_DRILLED_DOWN_CHART_HEIGHT}px"},
                                        config={"responsive": True},
                                    ),
                                    html.P(
                                        id="last-updated-callout-inverters-level4-subplot",
                                        className="last-updated-callout",
                                        style={"margin": 0},
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
        dcc.Store(id="power-perf-click-store2", data=None),
        dcc.Store(id="start-date-clean3", data=None),
        dcc.Store(id="end-date-clean3", data=None),
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="title-and-controls",
                    children=[
                        html.Span(
                            className="chart-title",
                            children=html.Span(
                                id="solar-inverters-treemap-title",
                                children="Comparison across Inverters",
                                className="title",
                            ),
                        ),
                        html.Div(
                            className="chart-control",
                            children=[
                                dbc.Tooltip(
                                    SOLAR_TREEMAP_TOOLTIP_TEXT_LOOKUP[PERFORMANCE_METRICS[0]],
                                    target=PERFORMANCE_METRICS[0],
                                    placement="bottom",
                                    class_name="metric-tooltip",
                                ),
                                dbc.Tooltip(
                                    SOLAR_TREEMAP_TOOLTIP_TEXT_LOOKUP[PERFORMANCE_METRICS[1]],
                                    target=PERFORMANCE_METRICS[1],
                                    placement="bottom",
                                    class_name="metric-tooltip",
                                ),
                                dbc.Tooltip(
                                    SOLAR_TREEMAP_TOOLTIP_TEXT_LOOKUP[PERFORMANCE_METRICS[2]],
                                    target=PERFORMANCE_METRICS[2],
                                    placement="bottom",
                                    class_name="metric-tooltip",
                                ),
                                dcc.RadioItems(
                                    id="solar-inverters-sort-by",
                                    className="right-floating-control",
                                    options=[
                                        {
                                            "label": "Lost Energy",
                                            "value": "lost_energy",
                                        },
                                        {
                                            "label": "Lost Revenue",
                                            "value": "lost_revenue",
                                        },
                                        {
                                            "label": "Relative Deviation",
                                            "value": "relative_deviation",
                                        },
                                    ],
                                    value="relative_deviation",
                                    labelStyle={"display": "inline-block"},
                                ),
                                dcc.RadioItems(
                                    id="solar-inverters-under-over-perform",
                                    className="under-over-perform",
                                    style={"marginRight": "0.75rem"},
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
                                acknowledge_control(
                                    _id="solar-acknowledged-inverters",
                                    label="Acknowledged Inverters",
                                    placeholder="Type to hide Inverters...",
                                ),
                            ],
                        ),
                    ],
                ),
                treemap_and_subcharts,
                html.P(
                    id="last-updated-callout-inverter-treemap",
                    className="last-updated-callout",
                ),
            ],
        ),
    ]
    return output


@callback(
    Output("last-updated-callout-inverter-treemap", "children"),
    Input("url", "pathname"),
)
def update_inverter_treemap_last_updated_callout(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.inverter_metrics"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the Inverter Treemap was Last Updated on {last_updated}."

@callback(
    Output("last-updated-callout-inverters-level1-subplot", "children"),
    Input("url", "pathname"),
)
def update_inverter_treemap_last_updated_callout_level1(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.clean_data"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the 'Irradiance-Capacity Regression' Plot was Last Updated on {last_updated}."

@callback(
    Output("last-updated-callout-inverters-level2-subplot", "children"),
    Input("url", "pathname"),
)
def update_inverter_treemap_last_updated_callout_level2(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.clean_data"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the 'Correlation Plot' was Last Updated on {last_updated}."

@callback(
    Output("last-updated-callout-inverters-level3-subplot", "children"),
    Input("url", "pathname"),
)
def update_inverter_treemap_last_updated_callout_level3(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.clean_data"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the 'Inverter's Deviation from Plant' Plot was Last Updated on {last_updated}."

@callback(
    Output("last-updated-callout-inverters-level4-subplot", "children"),
    Input("url", "pathname"),
)
def update_inverter_treemap_last_updated_callout_level4(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.clean_data"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the 'Inverter 10-Min Time Series' Plot was Last Updated on {last_updated}."

@callback(
    Output("inverters-treemap", "figure"),
    Output("solar-inverters-treemap-title", "children"),
    Output("inverters-performance-number-line", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("solar-inverters-under-over-perform", "value"),
    Input("solar-inverters-sort-by", "value"),
    Input("project-dropdown", "value"),
    Input("self-perform-checkbox", "value"),
    Input("solar-acknowledged-inverters", "value"),
    State("date-intervals-store", "data"),
)
def update_inverter_treemap(
    picker_start_date,
    picker_end_date,
    under_over_perform,
    sort_by,
    plant_filter,
    self_perform_checkbox,
    acknowleded_inverters,
    date_intervals_store,
):
    start_date = datetime.fromisoformat(picker_start_date)
    end_date = datetime.fromisoformat(picker_end_date)
    conn = Databricks_Repository()
    plant_arr = decide_plants_to_show(
        conn=conn,
        self_perform_checkbox=self_perform_checkbox,
        plant_filter=plant_filter,
    )

    df_inverters = conn.get_inverter_metrics(
        start_date=start_date,
        end_date=end_date,
        plant=plant_arr,
    )
    df_inverters = df_inverters[~df_inverters["element_name"].isin(acknowleded_inverters)]

    # generate the inverter performance chart
    treemap = gen_inverters_treemap(
        data_frame=df_inverters,
        metric=sort_by,
        under_over_perform=under_over_perform,
    )

    # generate the inverter performance number line
    numberline_chart = gen_inverters_number_line(
        data_frame=df_inverters,
        metric=sort_by,
        app_mode="solar",
    )

    # generate title for treemap
    title_start = start_date.strftime("%m/%d")
    title_end = end_date.strftime("%m/%d")
    dates_substring = f"({title_start} to {title_end})"
    sorting_metric = sort_by.replace("_", " ").title()

    substring_plant = gen_plant_subtitle(plant_arr)
    subtitle = f"{substring_plant}, {sorting_metric} {dates_substring}"
    title = f"{under_over_perform.title()} Inverters, {subtitle}"

    # count all items per trace
    pts_displayed_in_numberline = 0
    for trace in numberline_chart["data"]:
        pts_displayed_in_numberline += len(trace["x"])
    numberline_title = f"Displaying {pts_displayed_in_numberline} Inverters, {subtitle}"
    numberline_chart.update_layout(title=numberline_title)
    return treemap, title, numberline_chart


@callback(
    Output("start-date-clean3", "data"),
    Output("end-date-clean3", "data"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
)
def store_dates(
    picker_start_date,
    picker_end_date,
):
    start_date = datetime.fromisoformat(picker_start_date)
    end_date = datetime.fromisoformat(picker_end_date)
    return start_date, end_date


@callback(
    Output("power-perf-click-store2", "data"),
    Input("inverters-treemap", "clickData"),
    State("heatmap-box4", "className"),
)
def save_clicked_inverter(
    treemapClickData,
    subchart_cls,
):
    """Store the inverter tile we clicked in the treemap."""
    if not treemapClickData or subchart_cls == "is-open":
        return dash.no_update

    # figure out the name of the Inverter we clicked
    selected_target = treemapClickData["points"][0]["customdata"][0]
    return selected_target

@callback(
    Output("solar-inverters-level1-subplot", "figure"),
    Input("power-perf-click-store2", "data"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    State("date-intervals-store", "data"),
)
def load_level1_power_curve_subcharts(
    clicked_inverter,
    picker_start_date,
    picker_end_date,
    date_intervals_store,
):
    if picker_start_date is None or picker_end_date is None or clicked_inverter is None:
        return dash.no_update
    start_date = datetime.fromisoformat(picker_start_date)
    end_date = datetime.fromisoformat(picker_end_date)

    conn = Databricks_Repository()
    plant = extract_plant(clicked_inverter)
    df = conn.get_inverter_performance_power_online_filter(
        inverter=clicked_inverter,
        plant=plant,
        start_date=start_date,
        end_date=end_date,
    )
    fig = gen_level1_subchart(df=df, inverter=clicked_inverter)
    return fig

@callback(
    Output("solar-inverters-level2-subplot", "figure"),
    Input("power-perf-click-store2", "data"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    State("date-intervals-store", "data"),
)
def load_level2_power_curve_subcharts(
    clicked_inverter,
    picker_start_date,
    picker_end_date,
    date_intervals_store,
):
    if picker_start_date is None or picker_end_date is None or clicked_inverter is None:
        return dash.no_update
    start_date = datetime.fromisoformat(picker_start_date)
    end_date = datetime.fromisoformat(picker_end_date)

    conn = Databricks_Repository()
    plant = extract_plant(clicked_inverter)
    df = conn.get_inverter_performance_power_online_filter(
        inverter=clicked_inverter,
        plant=plant,
        start_date=start_date,
        end_date=end_date,
    )
    fig = gen_level2_subchart(df=df, inverter=clicked_inverter)
    return fig

@callback(
    Output("solar-inverters-level3-subplot", "figure"),
    Input("power-perf-click-store2", "data"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    State("date-intervals-store", "data"),
)
def load_level3_power_curve_subcharts(
    clicked_inverter,
    picker_start_date,
    picker_end_date,
    date_intervals_store,
):
    if picker_start_date is None or picker_end_date is None or clicked_inverter is None:
        return dash.no_update
    start_date = datetime.fromisoformat(picker_start_date)
    end_date = datetime.fromisoformat(picker_end_date)

    conn = Databricks_Repository()
    plant = extract_plant(clicked_inverter)
    df = conn.get_inverter_performance_power_online_filter(
        inverter=clicked_inverter,
        plant=plant,
        start_date=start_date,
        end_date=end_date,
    )
    fig = gen_level3_subchart(df=df, inverter=clicked_inverter)
    return fig

@callback(
    Output("solar-inverters-level4-subplot", "figure"),
    Input("power-perf-click-store2", "data"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    State("date-intervals-store", "data"),
)
def load_level4_inverter_subcharts(
    clicked_inverter,
    picker_start_date,
    picker_end_date,
    date_intervals_store,
):
    if picker_start_date is None or picker_end_date is None or clicked_inverter is None:
        return dash.no_update
    start_date = datetime.fromisoformat(picker_start_date)
    end_date = datetime.fromisoformat(picker_end_date)

    conn = Databricks_Repository()
    plant = extract_plant(clicked_inverter)
    df = conn.get_inverter_performance_power_no_online_filter(
        inverter=clicked_inverter,
        plant=plant,
        start_date=start_date,
        end_date=end_date,
    )
    fig = gen_level4_subchart(df=df, inverter=clicked_inverter)
    return fig

@callback(
    Output("heatmap-box4", "className"),
    Output("treemap-heatmap-box4", "className"),
    Input("inverters-treemap", "clickData"),
    Input("heatmap-toggle4", "value"),
    Input("start-date-clean3", "data"),
    Input("end-date-clean3", "data"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("project-dropdown", "value"),
    Input("solar-inverters-sort-by", "value"),
    Input("solar-inverters-under-over-perform", "value"),
    Input("solar-acknowledged-inverters", "value"),
    State("heatmap-box4", "className"),
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
    sort_by,
    under_over_perform,
    acknowledged_pp_turbines,
    last_subchart_cls,
):
    subchart_cls = last_subchart_cls
    if ctx.triggered_id is None:
        return dash.no_update
    elif ctx.triggered_id == "inverters-treemap":
        if last_subchart_cls == "is-closed":
            subchart_cls = "is-open"
        else:
            subchart_cls = "is-closed"
    elif ctx.triggered_id in (
        "date-picker-range",
        "project-dropdown",
        "solar-inverters-sort-by",
        "solar-inverters-under-over-perform",
        "solar-acknowledged-inverters",
    ):
        subchart_cls = "is-closed"

    if subchart_cls == "is-closed":
        treemap_cls = "treemap-subcharts-container"
        return subchart_cls, treemap_cls

    treemap_cls = "treemap-subcharts-container bottom-margin3"
    return subchart_cls, treemap_cls

@callback(
    Output("solar-acknowledged-inverters", "options"),
    Input("project-dropdown", "value"),
    Input("solar-inverters-sort-by", "value"),
)
def populate_inverters_dropdown_options(project_dropdown, sort_by):
    str_start_date = "2024-01-30"
    str_end_date = "2024-12-31"
    start_date = datetime.strptime(str_start_date, "%Y-%m-%d")
    end_date = datetime.strptime(str_end_date, "%Y-%m-%d")

    conn = Databricks_Repository()
    df_inverters = conn.get_inverter_metrics(
        start_date=start_date,
        end_date=end_date,
        plant=None
    )
    names = df_inverters["element_name"]
    return sorted(names)
