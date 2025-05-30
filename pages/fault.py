from datetime import datetime
import re

import dash
from dash import html, ctx, dcc, callback, Input, Output, State, Patch
import pandas as pd

from Charts.Heatmap import (
    generate_fault_heatmap,
)
from Charts.Treemap import (
    generate_fault_treemap,
)
from Charts.Plotters import (
    default_chart,
    generate_pebble_chart,
    generate_pulse_pareto_chart,
)
from Model.DataAccess import Databricks_Repository
from Utils.Components import (
    acknowledge_control,
)
from Utils.Transformers import (
    format_date_for_filename,
)
from Utils.UiConstants import (
    TURBINE_FAULT_CODE_COUNT,
    PEBBLE_CHART_METRICS,
    PARETO_COLORS,
    ALL_FAULT_CHART_METRICS,
    DESCRIPTION_CODE_DELIM,
)


def extract_customdata_index(text):
    """Extract the customdata index number from a hovertemplate line."""
    customdata_index = re.search(r"customdata\[(\d+)\]", text)
    if customdata_index:
        return int(customdata_index.group(1))
    return None

def extract_unit(text):
    """Extract the units from a hovertemplate line."""
    text = text.split("}")
    if len(text) <= 1:
        return ""
    text = text[-1]
    text = text.strip()
    return text


dash.register_page(
    __name__,
    path="/fault-analysis",
    title="Fault Analysis",
)


def layout():
    output = [
        dcc.Download(id="fault-treemap-download-reciever"),
        dcc.Store(id="start-date-clean", data=None),
        dcc.Store(id="end-date-clean", data=None),
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="fault-control-box",
                    children=dcc.RadioItems(
                        id="pebble-chart-metric",
                        className="pebble-chart-metric",
                        options=[
                            {"label": val, "value": val} for val in PEBBLE_CHART_METRICS
                        ],
                        value=PEBBLE_CHART_METRICS[0],
                        labelStyle={"display": "inline-block"},
                    ),
                ),
                dcc.Loading(
                    id="loading-pebble-chart",
                    type="graph",
                    overlay_style={
                        "opacity": 0.7,
                        "visibility":"visible",
                        "filter": "blur(2px)",
                    },
                    children=[
                        dcc.Graph(
                            id="pebble-chart",
                            figure=default_chart(bgcolor="#171717"),
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="fault-control-box",
                    children=[
                        html.Button(
                            id="download-fault-treemap-btn",
                            className="download-btn",
                            children="Download",
                        ),
                        dcc.RadioItems(
                            id="fault-treemap-metric",
                            options=[
                                {"label": val, "value": val}
                                for val in ALL_FAULT_CHART_METRICS
                            ],
                            value=ALL_FAULT_CHART_METRICS[0],
                            labelStyle={"display": "inline-block"},
                        ),
                    ],
                ),
                html.Div(
                    id="treemap-heatmap-box2",
                    className="treemap-subcharts-container",
                    children=[
                        dcc.Graph(
                            id="fault-treemap",
                            figure=default_chart(bgcolor="#171717"),
                        ),
                        html.Div(
                            id="heatmap-box2",
                            className="is-closed",
                            children=[
                                dcc.RadioItems(
                                    id="heatmap-toggle2",
                                    className="heatmap-toggle",
                                    options=[
                                        {
                                            "label": "By Fault",
                                            "value": "by-fault",
                                        },
                                        {
                                            "label": "By Turbine",
                                            "value": "by-turbine",
                                        },
                                    ],
                                    value="by-turbine",
                                    labelStyle={"display": "inline-block"},
                                ),
                                dcc.Graph(
                                    id="temp-heatmap2",
                                    figure={"data": [{"x": [1, 2, 3], "y": [4, 5, 6]}]},
                                    config={"displayModeBar": False},
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="title-and-controls",
                    children=[
                        html.Span(
                            className="chart-title",
                            children=[
                                html.Span(
                                    children="Fault Timeline",
                                    className="title",
                                ),
                                html.Span(
                                    children="",
                                    className="subtitle",
                                ),
                            ],
                        ),
                        html.Div(
                            className="chart-control",
                            children=[
                                dcc.RadioItems(
                                    id="pulse-pareto-metric",
                                    className="right-floating-control",
                                    options=[
                                        {"label": val, "value": val}
                                        for val in ALL_FAULT_CHART_METRICS
                                    ],
                                    value=ALL_FAULT_CHART_METRICS[0],
                                    labelStyle={"display": "inline-block"},
                                ),
                                acknowledge_control(
                                    _id="acknowledged-turbine-fault-pairs",
                                    label="Turbine-Faults to Hide",
                                    placeholder="Hide Turbine-Faults Pairs from the chart...",
                                ),
                            ],
                        ),
                    ],
                ),
                dcc.Graph(
                    id="pulse-pareto-chart",
                    figure=default_chart(bgcolor="#171717"),
                ),
            ],
        ),
    ]
    return output


@callback(
    Output("pebble-chart", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("pebble-chart-metric", "value"),
    Input("project-dropdown", "value"),
    Input("oem-dropdown", "value"),
    Input("acknowledged-fault-descriptions", "value"),
    Input("filter-faults-dropdown", "value"), #Allows for the Filter by Fault feature to work dynamically - Jylen Tate
    State("date-intervals-store", "data"),
)
def update_pebble_chart(
    start_date,
    end_date,
    metric,
    project,
    oem,
    acknowledged_faults,
    selected_fault,
    date_intervals_store,
):
    conn = Databricks_Repository()
    df_metric = conn.get_wind_fault_code_data(
        start_date=start_date,
        end_date=end_date,
    )
    pebble_chart = generate_pebble_chart(
        df_metric=df_metric,
        metric=metric,
        start=start_date,
        end=end_date,
        project=project,
        oem=oem,
        acknowledged_faults=acknowledged_faults,
        selected_fault=selected_fault,
    )
    return pebble_chart


@callback(
    Output("fault-treemap", "figure"),
    Output("start-date-clean", "data"),
    Output("end-date-clean", "data"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("fault-treemap-metric", "value"),
    Input("project-dropdown", "value"),
    Input("oem-dropdown", "value"),
    Input("acknowledged-fault-descriptions", "value"),
    Input("filter-faults-dropdown", "value"), #Allows for the Filter by Fault feature to work dynamically - Jylen Tate
    State("date-intervals-store", "data"),
)
def update_fault_treemap(
    start_date,
    end_date,
    metric, project, oem, acknowledged_faults, selected_fault, date_intervals_store
):
    conn = Databricks_Repository()
    df_metric = conn.get_wind_fault_code_data(
        start_date=start_date,
        end_date=end_date,
    )

    # TODO: Verify that this new logic for start and end dates preserves same behaviour
    start_date = start_date.split("T")[0]
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = end_date.split("T")[0]
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    fault_treemap = generate_fault_treemap(
        df_metric=df_metric,
        metric=metric,
        start=start_date,
        end=end_date,
        project=project,
        oem=oem,
        acknowledged_faults=acknowledged_faults,
        selected_fault = selected_fault
    )
    return fault_treemap, start_date, end_date


@callback(
    Output("temp-heatmap2", "figure"),
    Output("heatmap-box2", "className"),
    Output("treemap-heatmap-box2", "className"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("fault-treemap", "clickData"),
    Input("heatmap-toggle2", "value"),
    Input("fault-treemap-metric", "value"),
    Input("project-dropdown", "value"),
    Input("acknowledged-fault-descriptions", "value"),
    Input("filter-faults-dropdown", "value"), #Allows for the Filter by Fault feature to work dynamically - Jylen Tate
    State("heatmap-box2", "className"),
    State("date-intervals-store", "data"),
    prevent_inital_call=True,
)
def toggle_fault_treemap_subcharts(
    start_date,
    end_date,
    treemapClickData,
    heatmap_toggle,
    metric,
    project_dropdown,
    acknowledged_faults,
    selected_fault,
    last_heatmap_cls,
    date_intervals_store,
):
    heatmap_cls = last_heatmap_cls
    if ctx.triggered_id is None:
        return dash.no_update
    elif ctx.triggered_id == "fault-treemap":
        if last_heatmap_cls == "is-closed":
            heatmap_cls = "is-open"
        else:
            heatmap_cls = "is-closed"
    elif ctx.triggered_id in (
        "date-picker-range",
        "fault-treemap-metric",
        "project-dropdown",
        "filter-faults-dropdown",
        "acknowledged-fault-descriptions"
    ):
        heatmap_cls = "is-closed"

    if heatmap_cls == "is-closed":
        heatmap = default_chart(bgcolor="#171717")
        treemap_cls = "treemap-subcharts-container"
        return heatmap, heatmap_cls, treemap_cls

    label = treemapClickData["points"][0]["label"]
    project_turbine, fault_description = label.split("<br>")
    project = project_turbine.split("-")[0]
    turbine = project_turbine.split("-")[1]

    conn = Databricks_Repository()
    daily_dataset = conn.get_wind_fault_code_data(
        start_date=start_date,
        end_date=end_date,
    )

    # TODO: Verify that this new logic for start and end dates preserves same behaviour
    start_date = start_date.split("T")[0]
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = end_date.split("T")[0]
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    if heatmap_toggle == "by-fault":
        dataset = conn.get_wind_fault_downtime_lost_energy(
            start_date=start_date,
            end_date=end_date,
            plant=project_dropdown,
        )
        chart = generate_pulse_pareto_chart(
            fault_metrics_df=dataset,
            fault_daily_metrics_df=daily_dataset,
            start_date=start_date,
            end_date=end_date,
            metric=metric,
            project=project,
            turbine_arr=[project_turbine],
        )
        chart.update_layout(
            height=375,
        )
    elif heatmap_toggle == "by-turbine":
        dataset = conn.get_wind_fault_code_data(
            start_date=start_date,
            end_date=end_date,
        )
        chart = generate_fault_heatmap(
            dataset=dataset,
            metric=metric,
            fault_description=fault_description,
        )
    treemap_cls = "treemap-subcharts-container bottom-margin2"
    return chart, heatmap_cls, treemap_cls


@callback(
    Output("pulse-pareto-chart", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
    Input("pulse-pareto-metric", "value"),
    Input("project-dropdown", "value"),
    Input("acknowledged-turbine-fault-pairs", "value"),
    Input("acknowledged-fault-descriptions", "value"),
    Input("filter-faults-dropdown", "value"),
    Input("oem-dropdown", "value"),
    State("date-intervals-store", "data"),
    State("pulse-pareto-chart", "figure"),
)
def update_pulse_pareto_chart(
    start_date,
    end_date,
    metric,
    project,
    ack_turbine_fault_pairs,
    ack_fault_descr_pairs,
    filter_fault_descr_pairs,
    oem,
    date_intervals_store,
    lastFigure,
):
    conn = Databricks_Repository()
    dataset = conn.get_wind_fault_downtime_lost_energy(
        start_date=start_date,
        end_date=end_date,
        plant=project,
        ack_turbine_fault_pairs=ack_turbine_fault_pairs,
        ack_fault_descr_pairs=ack_fault_descr_pairs,
        filter_fault_descr_pairs=filter_fault_descr_pairs,
    )
    daily_dataset = conn.get_wind_fault_code_data(
        start_date=start_date,
        end_date=end_date,
        ack_turbine_fault_pairs=ack_turbine_fault_pairs,
        ack_fault_descr_pairs=ack_fault_descr_pairs,
        filter_fault_descr_pairs=filter_fault_descr_pairs,
    )

    start_date = start_date.split("T")[0]
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = end_date.split("T")[0]
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    chart = generate_pulse_pareto_chart(
        fault_metrics_df=dataset,
        fault_daily_metrics_df=daily_dataset,
        start_date=start_date,
        end_date=end_date,
        metric=metric,
        project=project,
        num_of_rows=TURBINE_FAULT_CODE_COUNT,
        oem=oem,
    )
    return chart


@callback(
    Output("acknowledged-turbine-fault-pairs", "options"),
    Input("url", "pathname"),
)
def populate_pareto_acknowledge_dropdown_options(pathname):
    """The options are of the form '{turbine} - {code}', ex. 'BR2-K001 - 2'."""
    parsed_pathname = dash.strip_relative_path(pathname)
    if parsed_pathname == "fault-analysis":
        conn = Databricks_Repository()
        turbine_fault_codes = conn.get_wind_turbine_fault_codes()
        return turbine_fault_codes
    return dash.no_update


@callback(
    Output("acknowledged-fault-descriptions", "options"),
    Input("url", "pathname"),
)
@callback(
    Output("filter-faults-dropdown", "options"),
    Input("url", "pathname"),
)
def populate_global_fault_acknowledge_dropdowns(pathname):
    """The options are of the form '{code} | {description}', ex. '5 | REPAIR'."""
    parsed_pathname = dash.strip_relative_path(pathname)
    if parsed_pathname == "fault-analysis":
        conn = Databricks_Repository()
        fault_description_options = conn.get_wind_fault_code_description_options()
        return fault_description_options
    return dash.no_update


@callback(
    Output("fault-treemap-download-reciever", "data"),
    Input("download-fault-treemap-btn", "n_clicks"),
    State("fault-treemap", "figure"),
    State("project-dropdown", "value"),
    State("start-date-clean", "data"),
    State("end-date-clean", "data"),
    prevent_initial_call=True,
)
def download_fault_treemap_dataset(
    n_clicks, fault_treemap_json, project, start_date, end_date
):
    if n_clicks is None:
        return dash.no_update

    num_of_rows = 10
    customdata_order = (
        "Turbine",
        "Fault",
        "Downtime (Hours)",
        "Lost Revenue ($)",
        "Lost Energy (MWh)",
        "Count",
    )

    customdata = fault_treemap_json["data"][0]["customdata"]
    hovertemplate = fault_treemap_json["data"][0]["hovertemplate"]

    # look at information in the figure directly to build the data output reliably
    df_rows = []
    hovertemplate_lines = hovertemplate.split("<br>")
    if hovertemplate_lines[-1].startswith("<extra"):
        hovertemplate_lines = hovertemplate_lines[:-1]
    for row in customdata[:num_of_rows]:
        lookup = {}
        for idx, line in enumerate(hovertemplate_lines):
            # extract label (add units if they exist)
            label = line.split(":")[0]
            label = label.strip()
            unit = extract_unit(line)

            # Lost Revenue uses a special notation so we account for this special case
            if unit == ")" or "revenue" in label.lower():
                label = f"{label} ($)"
            elif unit != "":
                label = f"{label} ({unit})"

            # extract index location to track down what this metric is
            customdata_idx = extract_customdata_index(line)

            lookup[label] = row[customdata_idx]
        df_rows.append(lookup)
    df = pd.DataFrame(df_rows)

    start_date_fmt = format_date_for_filename(start_date)
    end_date_fmt = format_date_for_filename(end_date)

    project_fmt = project
    if project == "All":
        project_fmt = "all_projects"
    project_fmt = project_fmt.replace(" ", "")
    filename = (
        f"{start_date_fmt}_to_{end_date_fmt}_treemap_fault_dataset_{project_fmt}.xlsx"
    )

    return dcc.send_data_frame(df.to_excel, filename, sheet_name="Sheet1")
