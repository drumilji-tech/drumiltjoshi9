"""Drilled Down Sub Charts."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .Helpers import (
    extract_metric,
    extract_plant,
    extract_measurement,
    extract_power_conversion_station,
    extract_weather_station,
)
from Utils.ISightConstants import (
    REVERSE_DATABASE_METRIC_TRANSLATOR,
    MEASUREMENT_UNITS_LOOKUP,
)
from Utils.UiConstants import (
    PARETO_COLORS,
)

WEATHER_STATION_COLORS = px.colors.qualitative.Vivid
REFERENCE_LINE_STYLE = {
    "color": "#00FE35",
    "dash": "dashdot",
}
SOLAR_DRILLED_DOWN_CHART_LEGEND = dict(
    orientation="h",
    y=1,
    x=0,
    xanchor="left",
    yanchor="bottom",
)


def generate_metrics_sparkline(df, tag, clear_sky_df, start_date, end_date):
    """
    Create a chart showcasing each metric of one weather station measurement.

    This chart appears in the UI after you click on one of the tornado bars
    within one of the available tornado charts.

    Args:
        df (pandas.DataFrame): The data that comes from
            `Databricks_Repository.get_daily_values_for_weather_station`.
        tag (str): The full PI tag of the tornado bar that the user clicked
            to open this chart in the first place.
        start_date (datetime.datetime): The start date of the dateset `df`.
            Note that this value is only used for display in the title.
        end_date (datetime.datetime): The end date of the dateset `df`.
            Note that this value is only used for display in the title.

    Returns:
        (plotly.graph_objects.Figure): A plotly sparklines chart.
    """
    def _try_rounding_non_ints(val):
        if not isinstance(val, int):
            try:
                val = round(val)
            except:
                pass
        return val

    merged_df = pd.merge(df, clear_sky_df[["date", "is_clear_sky_day"]], on="date", how="left")
    merged_df["is_clear_sky_day"] = merged_df["is_clear_sky_day"].fillna(0).astype(int)

    col_label_lookup = {}
    metric_tag_to_col = {}
    for col in df.columns:
        if col.lower() == "date":
            continue
        metric_tag = "_".join(col.split("_")[1:])
        if metric_tag not in REVERSE_DATABASE_METRIC_TRANSLATOR:
            continue
        metric_tag_to_col[metric_tag] = col
    for metric_tag, metric_name in REVERSE_DATABASE_METRIC_TRANSLATOR.items():
        if metric_tag in metric_tag_to_col:
            col = metric_tag_to_col[metric_tag]
            col_label_lookup[col] = metric_name

    fig = make_subplots(
        rows=len(col_label_lookup),
        cols=1,
        subplot_titles=[col_label_lookup[c].title() for c in col_label_lookup.keys()],
        vertical_spacing=0.1,
    )

    colors_arr = WEATHER_STATION_COLORS
    for idx, col in enumerate(col_label_lookup.keys()):
        metric_name = col_label_lookup[col]
        color = colors_arr[idx]

        size_arr = np.where(merged_df["is_clear_sky_day"], 7, 3)
        text_arr = np.where(merged_df["is_clear_sky_day"], "Yes", "No")
        line_trace = go.Scattergl(
            x=merged_df["date"],
            y=merged_df[col],
            mode="markers+lines",
            name=metric_name.title(),
            text=text_arr,
            marker=dict(size=size_arr, color=color),
            line=dict(width=1, color=color),
            hovertemplate="<b>Date</b>: %{x}<br><b>Value</b>: %{y}<br><b>Clear Sky</b>: %{text}<extra></extra>",
            opacity=1,
            legendgroup=metric_name,
            showlegend=False,
        )
        fig.add_trace(
            line_trace,
            row=idx + 1,
            col=1,
        )

    # highlight the regions where there is clear sky
    merged_df["date"] = pd.to_datetime(merged_df["date"])
    clear_sky_ranges = []
    is_in_range = False
    start = None
    for i, row in merged_df.iterrows():
        if row["is_clear_sky_day"] == 1 and not is_in_range:
            start = row["date"]
            is_in_range = True
        elif row["is_clear_sky_day"] == 0 and is_in_range:
            if start == merged_df.iloc[i - 1]["date"]:
                end = f"{start.strftime('%Y-%m-%d')} 12"
            else:
                end = merged_df.iloc[i - 1]["date"]
            clear_sky_ranges.append((start, end))
            is_in_range = False
    if is_in_range:
        last_date = merged_df.iloc[-1]["date"]
        end = f"{last_date.strftime('%Y-%m-%d')} 12"
        clear_sky_ranges.append((start, end))
    merged_df["date"] = merged_df["date"].dt.strftime("%Y-%m-%d")

    for dates in clear_sky_ranges:
        x0 = dates[0]
        x1 = dates[1]
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor=PARETO_COLORS["highlight"],
            opacity=0.15,
            layer="below",
            line_width=0,
        )

    # construct the title for the chart
    plant_label = extract_plant(tag)
    ws_label = extract_weather_station(tag)
    meas_label = extract_measurement(tag)
    fmt_ws_title = f"{plant_label}-{ws_label}"
    title_start = start_date.strftime("%m/%d")
    title_end = end_date.strftime("%m/%d")
    fmt_date_range = f"({title_start} to {title_end})"
    title = f"All {meas_label} Metrics for {fmt_ws_title} by Day {fmt_date_range}"

    fig.update_layout(
        title=title,
        template="plotly_dark",
        autosize=True,
        margin=dict(
            autoexpand=True,
        ),
        plot_bgcolor="#181818",
        xaxis=dict(tickfont=dict(color="#eee", size=10)),
        yaxis=dict(
            tickfont=dict(color="#eee", size=10),
            exponentformat="SI",
        ),
    )
    fig.update_xaxes(dict(showgrid=False))
    fig.update_yaxes(dict(showgrid=False))
    return fig


def generate_all_ws_per_plant_chart(df, tag, start_date, end_date):
    """Create a chart of the weather stations trendlines in a single plant.

    This chart appears in the UI after you click on one of the tornado bars
    within one of the available tornado charts.

    Args:
        df (pandas.DataFrame): A dataset that has come from the metrics table
            in the Databricks Repository.
        tag (str): The full PI tag of the tornado bar that the user clicked
            to open this chart in the first place.
        start_date (datetime.datetime): The start date of the dateset `df`.
            Note that this value is only used for display in the title.
        end_date (datetime.datetime): The end date of the dateset `df`.
            Note that this value is only used for display in the title.

    Returns:
        (plotly.graph_objects.Figure): A plotly figure with multiple scatter
            traces in line mode.
    """
    clicked_weather_station = extract_weather_station(tag)

    ordered_cols = list(df.columns)
    if "date" in ordered_cols:
        ordered_cols.remove("date")

    idx = ordered_cols.index(tag)
    ws = ordered_cols.pop(idx)
    ordered_cols.append(ws)

    fig = go.Figure()
    color_idx = 0
    for idx, col in enumerate(ordered_cols):
        ws_label = extract_weather_station(col)
        if ws_label == clicked_weather_station:
            opacity = 1
            mode = "markers+lines"
            color = PARETO_COLORS["highlight"]
        else:
            opacity = 0.85
            mode = "lines"
            color = WEATHER_STATION_COLORS[color_idx % len(WEATHER_STATION_COLORS)]
            color_idx += 1
        trace = go.Scattergl(
            x=df["date"],
            y=df[col],
            mode=mode,
            name=ws_label,
            opacity=opacity,
            marker=dict(
                color=color,
            ),
            line=dict(
                color=color,
            )
        )
        fig.add_trace(trace)

    # construct the title for the chart
    plant_label = extract_plant(tag)
    meas_label = extract_measurement(tag)
    metric_label = extract_metric(tag)
    title_start = start_date.strftime("%m/%d")
    title_end = end_date.strftime("%m/%d")
    fmt_date_range = f"({title_start} to {title_end})"
    title = f"{len(df.columns)-1} Weather Stations from Plant {plant_label} showing Daily {meas_label} {fmt_date_range}"

    fig.update_layout(
        title=title,
        template="plotly_dark",
        autosize=True,
        margin=dict(
            autoexpand=False,
        ),
        legend=SOLAR_DRILLED_DOWN_CHART_LEGEND,
        plot_bgcolor="#181818",
        hovermode="x",
        xaxis=dict(tickfont=dict(color="#eee", size=10)),
        yaxis=dict(
            tickfont=dict(color="#eee", size=10),
            exponentformat="SI",
            title=f"{meas_label} w/ {metric_label}",
        ),
    )
    fig.update_xaxes(dict(showgrid=False))
    fig.update_yaxes(dict(showgrid=False))
    return fig

def generate_ws_time_series(df, tag):
    """Create a chart of the 10-minute data for a weather station.
    
    Args:
        df (pd.DataFrame): The output of the following method:
            `Databricks_Repository.get_weather_station_time_series`.
        tag (str): The full PI tag for the weather station time
            series we are intending to plot.
    """
    measurement = extract_measurement(tag)
    plant = extract_plant(tag)
    pcs = extract_power_conversion_station(tag)
    ws = extract_weather_station(tag)
    name = f"{plant}-{pcs}-{ws}"
    units = MEASUREMENT_UNITS_LOOKUP[measurement]

    trace_array = []
    highlighted_trace_index = None

    index = 0
    color_idx = 0
    for g in df.groupby("element_name"):
        this_name = g[0]
        dff = g[1]

        if (
                ws == extract_weather_station(this_name)
            and pcs == extract_power_conversion_station(this_name)
        ):
            line_color = PARETO_COLORS["highlight"]
            line_dash = "solid"
            highlighted_trace_index = index
        elif "SolarAnywhereData" in this_name:
            if measurement == "BOM":
                dff["value"] = dff["value"].replace(0, np.nan)
            line_color = REFERENCE_LINE_STYLE["color"]
            line_dash = REFERENCE_LINE_STYLE["dash"]
        else:
            line_color = WEATHER_STATION_COLORS[color_idx % len(WEATHER_STATION_COLORS)]
            line_dash = "solid"
            color_idx += 1

        trace = go.Scattergl(
            mode="lines",
            x=dff["time"],
            y=dff["value"],
            name=this_name,
            marker=dict(color=line_color),
            line=dict(color=line_color, dash=line_dash),
            hovertemplate="Time: %{x}<br>" + measurement + ": %{y} " + units,
        )
        trace_array.append(trace)
        index += 1

    # ensure the highlighted weather station is drawn on top of the others
    if highlighted_trace_index is not None:
        last_trace = trace_array.pop(highlighted_trace_index)
        trace_array.append(last_trace)

    fig = go.Figure(
        data=trace_array,
        layout={}
    )
    fig.update_layout(
        title=f"{name}: 10-Minute {measurement} Time Series",
        xaxis=dict(title="Time"),
        yaxis=dict(title=f"{measurement} ({units})"),
        template="plotly_dark",
        autosize=True,
        hovermode="x",
        legend=SOLAR_DRILLED_DOWN_CHART_LEGEND,
    )
    return fig
