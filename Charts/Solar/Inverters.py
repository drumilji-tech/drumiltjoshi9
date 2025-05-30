"""Charting Functions for the Inverters Page."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from Charts.Solar.Helpers import (
    extract_plant,
    extract_block,
    extract_power_conversion_station,
    extract_inverter,
)
from Charts.Treemap import (
    POWER_PERF_COLORSCALE,
    MARGIN_RIGHT,
)
from Utils.UiConstants import (
    DEFAULT_CHART_HEIGHT,
    PERFORMANCE_METRICS_LABEL_LOOKUP,
)
from Utils.ISightConstants import (
    SOLAR_INVERTER_METRIC_UNITS_LOOKUP,
)


INVERTER_PERFORMANCE_COLORSCALE = px.colors.diverging.Fall
INVERTER_PERFORMANCE_COLOR_OVERPERFORMING = INVERTER_PERFORMANCE_COLORSCALE[0]
INVERTER_PERFORMANCE_COLOR_UNDERPERFORMING = INVERTER_PERFORMANCE_COLORSCALE[-1]

# colors are derived from the POWER_CURVE_COLOR constants to parallel the Wind side
INVERTER_COLUMN_STYLING_LOOKUP = {
    "ActivePower": {
        "color": px.colors.qualitative.D3[0],
        "name": "Active Power",
        "symbol": "circle",
        "opacity": 0.8,
    },
    "ActivePowerExpected": {
        "color": px.colors.qualitative.D3[1],
        "name": "Expected Power",
        "symbol": "circle",
        "opacity": 0.8,
    },
    "ActivePowerNormalized": {
        "color": "#EEEEEE",
        "name": "Denormalized Inverter Power Avg",
        "symbol": "circle",
        "opacity": 0.8,
    },
}



gain_symbol = "(Gain)"
loss_symbol = ""
tooltip_footer = "NB. A negative number for a 'Lost' metric means there was a 'Gain'."

def _format_column(column):
    plant = extract_plant(column)
    block = extract_block(column)
    pcs = extract_power_conversion_station(column)
    inverter = extract_inverter(column)
    return "-".join([plant, block, pcs]) + " " + inverter

def _format_metric_as_label(metric):
    """Format the metric column names for display in the treemap."""
    clean_metric_label = metric
    clean_metric_label = clean_metric_label.replace("aggr_", "")
    clean_metric_label = clean_metric_label.replace("_", " ")
    clean_metric_label = clean_metric_label.title()
    return clean_metric_label

def _create_hint(metric):
    """Take a metric value, and craft a piece of text to explain it."""
    if metric < 0:
        return gain_symbol
    elif metric > 0:
        return loss_symbol
    else:
        return ""


def gen_inverter_performance_hovertemplate(data_frame, df_columns):
    element_name_idx = list(data_frame.columns).index("element_name")
    hovertemplate = "<b>%{customdata[" + str(element_name_idx) + "]}</b><br>"
    for column in df_columns:
        if column == "element_name":
            continue
        column_sans_aggr = column.replace("aggr_", "")

        label = _format_metric_as_label(column)
        idx = df_columns.index(column)

        try:
            blurb_idx = list(data_frame.columns).index("blurb_" + column)
            blurb_hovertemplate = " %{customdata[" + f"{blurb_idx}" + "]}"
        except ValueError:
            blurb_hovertemplate = ""

        try:
            units = SOLAR_INVERTER_METRIC_UNITS_LOOKUP[column_sans_aggr]
        except KeyError:
            units = ""

        if units != "":
            units = f"({units})"
        hovertemplate += f"{label} {units}: "
        hovertemplate += "%{customdata[" + f"{idx}" + "]:,.0f}"
        hovertemplate += blurb_hovertemplate
        hovertemplate += "<br>"
    hovertemplate += f"<br>{tooltip_footer}"
    return hovertemplate

def _prepare_data_for_inverter_perf_chart(data_frame, metric, tiles_to_display, app_mode):
    """Prepare data for use in performance inverter charts.
    
    Args:
        app_mode (str): Either 'wind' or 'solar'. This param is
            used for deciding what to expect with the format
            of the element names. Since this function is used
            in both the wind and solar side of the app, it
            must be able to accomodate for Inverters, and
            for Turbines.
    """
    df_columns = data_frame.columns
    df_columns = list(df_columns)
    aggr_colname = f"aggr_{metric}"

    if tiles_to_display is None:
        tiles_to_display = 25

    for col in df_columns:
        if "element_name" in col or "recovery" in col or "deviation" in col:
            continue
        new_colname = f"blurb_{col}"
        data_frame[new_colname] = data_frame[col].apply(_create_hint)

    if app_mode == "solar":
        data_frame["name"] = data_frame["element_name"].apply(_format_column)
        data_frame["abbrev-name"] = data_frame["element_name"].apply(lambda x: " ".join([extract_plant(x), extract_inverter(x)]))
    else:
        data_frame["name"] = data_frame["element_name"]
        data_frame["abbrev-name"] = data_frame["element_name"]
    data_frame["abs_deviation"] = data_frame[aggr_colname].apply(lambda x: abs(x))
    return data_frame, df_columns, aggr_colname, tiles_to_display

def gen_inverters_treemap(
    data_frame,
    metric,
    under_over_perform,
    tiles_to_display=None,
):
    """Create a treemap that shows the top offendending inverters.
    
    Args:
        data_frame (pd.DataFrame): The result from
            calling the `get_inverter_metrics` method.
        metric (str): One of "lost_energy", "lost_revenue",
            or "relative_deviation". This param determines the
            sorting of the inverters, but all metrics in the
            inputted `data_frame` and displayed in the tooltip
            of each treemap tile.
        under_over_perform (str): Determines whether
            to only show the underperforming vs the
            overperforming turbines relative to the
            benchmark. Either "overperforming" or
            "underperforming".
        tiles_to_display (int): Limit the top number
            of inverters to show. Defaults to 25.

    Returns:
        treemap (plotly.graph_objects.Figure): A plotly-ready
            Treemap figure made up of tiles, each representing
            an inverter.
    """
    df = data_frame.copy()
    df, df_columns, aggr_colname, tiles_to_display  = _prepare_data_for_inverter_perf_chart(
        df, metric, tiles_to_display, "solar",
    )

    if (
        (under_over_perform == "overperforming" and metric == "relative_deviation") or
        (under_over_perform == "underperforming" and "lost" in metric)
    ):
        df = df[df[aggr_colname] > 0]
    else:
        df = df[df[aggr_colname] <= 0]

    df = df.sort_values(
        by="abs_deviation",
        ascending=False
    ).head(tiles_to_display)

    # reverse the colorscale when toggling between over/under-performing
    red_green_colorscale =  INVERTER_PERFORMANCE_COLORSCALE
    if under_over_perform == "underperforming":
        colorscale =  [[0, "rgb(255,255,255)"], [1, INVERTER_PERFORMANCE_COLOR_UNDERPERFORMING]]
    else:
        colorscale =  [[0, "rgb(255,255,255)"], [1, INVERTER_PERFORMANCE_COLOR_OVERPERFORMING]]
    treemap = px.icicle(
        df,
        names="name",
        parents=["" for idx in df["name"]],
        values="abs_deviation",
        color_continuous_scale=colorscale,
        color="abs_deviation",
        template="plotly_dark",
        hover_data=df.columns,
    )
    treemap.update_layout(
        coloraxis=dict(colorbar=dict(title=dict(text="Abs. Deviation")))
    )

    hovertemplate = gen_inverter_performance_hovertemplate(df, df_columns)
    treemap.update_traces(
        pathbar=dict(visible=False),
        hovertemplate=hovertemplate,
    )
    treemap.update_layout(
        height=150,
        uniformtext=dict(minsize=22),
        margin=dict(
            autoexpand=False,
            t=18,
            b=0,
            l=0,
            r=MARGIN_RIGHT,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    treemap.update_traces(
        insidetextfont_size=20,
        root=dict(color="#232323"),
        tiling=dict(orientation="v"),
    )
    if under_over_perform == "overperforming":
        treemap.update_traces(
            tiling=dict(flip="x"),
        )
    return treemap


def gen_inverters_number_line(
    data_frame,
    metric,
    tiles_to_display=None,
    app_mode=None,
):
    """Create a chart that shows all the inverters at once.
    
    Args:
        data_frame (pd.DataFrame): The result from
            calling the `get_inverter_metrics` method.
        metric (str): One of "lost_energy", "lost_revenue",
            or "relative_deviation". This param determines the
            sorting of the inverters, but all metrics in the
            inputted `data_frame` and displayed in the tooltip
            of each treemap tile.
        tiles_to_display (int): Decide the number of both under- and
            over- performing inverters to color-code in the chart.
        app_mode (str): Either "wind" or "solar".

    Returns:
        treemap (plotly.graph_objects.Figure): A plotly-ready
            Treemap figure made up of tiles, each representing
            an inverter.
    """
    def gen_partitioned_data(data_frame, count, agg_column, flip=False):
        """Generate the top, middle, and bottom data for traces.

        The reason for splitting the incoming data is for the
        purpose of coloring the data points differently.
        """
        if not flip:
            # Normal case
            top_df = data_frame.nlargest(count, agg_column)
            top_df = top_df[top_df[agg_column] > 0]

            bottom_df = data_frame.nsmallest(count, agg_column)
            bottom_df = bottom_df[bottom_df[agg_column] < 0]
        else:
            # Flipped case (when "lost" in metric)
            top_df = data_frame.nsmallest(count, agg_column)
            top_df = top_df[top_df[agg_column] < 0]

            bottom_df = data_frame.nlargest(count, agg_column)
            bottom_df = bottom_df[bottom_df[agg_column] > 0]

        # Get middle performers
        excluded_indices = set(top_df.index).union(set(bottom_df.index))
        middle_df = data_frame.loc[~data_frame.index.isin(excluded_indices)]

        return top_df, bottom_df, middle_df

    df = data_frame.copy()
    df = df.rename(
        columns={
            "Turbine": "element_name",
            "lost_energy": "aggr_lost_energy",
            "lost_revenue": "aggr_lost_revenue",
            "daily_relative_deviation": "aggr_relative_deviation",
        }
    )
    if metric in PERFORMANCE_METRICS_LABEL_LOOKUP:
        metric = PERFORMANCE_METRICS_LABEL_LOOKUP[metric]
        metric = metric.lower()
        metric = metric.replace(" ", "_")

    df, df_columns, aggr_colname, tiles_to_display  = _prepare_data_for_inverter_perf_chart(
        df, metric, tiles_to_display, app_mode
    )

    underperform_color = INVERTER_PERFORMANCE_COLOR_UNDERPERFORMING
    overperform_color = INVERTER_PERFORMANCE_COLOR_OVERPERFORMING
    neutral_color = "#FFF"

    fig = go.Figure()

    # add a y=0 reference line
    fig.add_vline(x=0, line_width=3, line_dash="solid", line_color="#555")

    # Since "lost energy" or "lost revenue" means a positive val, we must flip the signs
    flip_inequality = ("lost" in metric)

    top_df, bottom_df, middle_df = gen_partitioned_data(
        df, 
        tiles_to_display, 
        aggr_colname, 
        flip=flip_inequality
    )
    for df, name, color, rank, mode in [
        (middle_df, "Other Inverters", neutral_color, 999, "markers"),
        (top_df, f"Top {len(top_df)} Performing Inverters", overperform_color, 1000, "markers+text"),
        (bottom_df, f"Bottom {len(bottom_df)} Performing Inverters", underperform_color, 998, "markers"),
    ]:
        fig.add_trace(go.Scatter(
            mode=mode,
            name=name,
            x=df[aggr_colname],
            y=[0] * len(df),
            marker=dict(color=color),
            customdata=df.values.tolist(),
            legendrank=rank
        ))

    fig.update_layout(
        template="plotly_dark",
        margin=dict(
            autoexpand=True,
            t=80,
            b=0,
            l=0,
            r=MARGIN_RIGHT,
        ),
        height=200,
        xaxis=dict(title=metric.title().replace("_", " ")),
        yaxis=dict(visible=False),
        legend=dict(orientation="h", yanchor="bottom", y=1)
    )

    hovertemplate = gen_inverter_performance_hovertemplate(df, df_columns)
    fig.update_traces(hovertemplate=hovertemplate)
    return fig

def style_treemap_subchart(fig):
    """Style the subchart belonging to the Inverter Treemaps.

    Args:
        fig (plotly.graph_objects.Figure): A Plotly figure.
    Returns:
        (plotly.graph_objects.Figure): A Plotly figure.
    """
    return fig.update_layout(
        template="plotly_dark",
        bargap=0.2,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.1,
        ),
    )

def safe_max(array, fallback=None):
    """Safely find the max of an array."""
    if fallback is None:
        fallback = 0
    try:
        return max(array)
    except ValueError:
        return fallback


def gen_level1_subchart(df, inverter):
    """Create charts that visualize Active Power against POA.

    Args:
        df (pandas.DataFrame): The output of the method
            `Databricks_Repository.get_inverter_performance_power_online_filter`.
        inverter (str): The name of the inverter of interest. This
            will display in titles to let the user know what we
            are looking at.

    Returns:
        fig (plotly.graph_objects.Figure): A Plotly figure that
            contains two subcharts.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=False,
        row_heights=[
            0.75,
            0.25,
        ],
    )

    poa_vals = df["IrradiancePOAAverage"]
    time_vals = df["start_time_utc"]

    # add the top subchart
    for column in INVERTER_COLUMN_STYLING_LOOKUP:
        name = INVERTER_COLUMN_STYLING_LOOKUP[column]["name"]
        color = INVERTER_COLUMN_STYLING_LOOKUP[column]["color"]
        symbol = INVERTER_COLUMN_STYLING_LOOKUP[column]["symbol"]
        opacity = INVERTER_COLUMN_STYLING_LOOKUP[column]["opacity"]
        hovertemplate = "<b>" + name + "</b>: %{y}<br><b>Irradiance POA Avg</b>: %{x}<br><b>Start Time</b>: %{text}<extra></extra>"
        fig.add_trace(go.Scatter(
            x=poa_vals,
            y=df[column],
            mode='markers',
            text=time_vals,
            hovertemplate=hovertemplate,
            marker=dict(color=color, symbol=symbol, opacity=opacity),
            name=name,
        ), row=1, col=1)
    fig.update_xaxes(title_text="POA Irradiance (W/m²)", row=1, col=1)
    fig.update_yaxes(title_text="Power (kW)", row=1, col=1)

    # add the bottom subchart
    fig.add_trace(go.Histogram(
        x=poa_vals,
        xbins=dict(size=20),
        marker=dict(color="#D6D6D6"),
        name="Irradiance Histogram",
        showlegend=False,
        hoverlabel={"namelength": -1},
    ), row=2, col=1)
    fig.update_xaxes(title_text="POA Irradiance (W/m²)", row=2, col=1)
    fig.update_yaxes(title_text="Frequency", row=2, col=1)
    
    # style the entire figure
    fig.update_xaxes(dtick=100)
    fig = style_treemap_subchart(fig)
    fig.layout.xaxis.matches = "x2"
    return fig

def gen_level2_subchart(df, inverter):
    """Create the level2 subchart in the inverter treemap.

    Args:
        df (pandas.DataFrame): The output of the method
            `Databricks_Repository.get_inverter_performance_power_online_filter`.
        inverter (str): The name of the inverter of interest.

    Returns:
        fig (plotly.graph_objects.Figure): A Plotly figure that
            contains two subcharts.
    """
    fig = go.Figure()

    # add a y=x line for reference
    max_ap = safe_max(df["ActivePower"])
    max_ap_exp = safe_max(df["ActivePowerExpected"])
    max_ap_norm = safe_max(df["ActivePowerNormalized"])
    max_val = max([
        max_ap,
        max_ap_exp,
        max_ap_norm,
    ])
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode="lines",
        name="y=x",
        hoverinfo="skip",
        showlegend=True,
        marker=dict(color="#555"),
        line=dict(width=3, dash="solid", color="#555"),
    ))

    for column in ["ActivePowerExpected", "ActivePowerNormalized"]:
        color = INVERTER_COLUMN_STYLING_LOOKUP[column]["color"]
        name = INVERTER_COLUMN_STYLING_LOOKUP[column]["name"]
        opacity = INVERTER_COLUMN_STYLING_LOOKUP[column]["opacity"]
        fig.add_trace(go.Scatter(
            x=df[column],
            y=df["ActivePower"],
            mode='markers',
            marker=dict(color=color, opacity=opacity),
            hovertemplate=f"<b>{inverter}</b><br>" + "Y: %{y}<br>X: %{x}<extra></extra>",
            name=name,
        ))

    # style the figure
    fig.update_xaxes(title_text="Expected AND/OR Denormalized Power (kW)")
    fig.update_yaxes(title_text="Raw Active Power (kW)")
    fig = style_treemap_subchart(fig)
    return fig

def gen_level3_subchart(df, inverter):
    """Create the level3 subchart in the inverter treemap.

    Args:
        df (pandas.DataFrame): The output of the method
            `Databricks_Repository.get_inverter_performance_power_online_filter`.
        inverter (str): The name of the inverter of interest.

    Returns:
        fig (plotly.graph_objects.Figure): A Plotly figure that
            contains two subcharts.
    """
    fig = go.Figure()

    # add a y=x line for reference
    ap_norm = safe_max(df["ActivePowerNormalized"])
    ap_norm_avg = safe_max(df["InverterActivePowerNormalizedAverage"])
    max_val = max([
        ap_norm,
        ap_norm_avg,
    ])
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode="lines",
        name="y=x",
        hoverinfo="skip",
        showlegend=True,
        marker=dict(color="#555"),
        line=dict(width=3, dash="solid", color="#555"),
    ))

    color = px.colors.qualitative.D3[6]
    name = "Plant vs Inverter Active Power Normalized"
    opacity = 0.8
    fig.add_trace(go.Scatter(
        x=df["InverterActivePowerNormalizedAverage"],
        y=df["ActivePowerNormalized"],
        mode='markers',
        marker=dict(color=color, opacity=opacity),
        hovertemplate=f"<b>{inverter}</b><br>" + "Y: %{y}<br>X: %{x}<extra></extra>",
        name=name,
    ))

    # style the figure
    fig.update_yaxes(title_text="Inverter Active Power Normalized (kW)")
    fig.update_xaxes(title_text="Plant Active Power Normalized (kW)")
    fig = style_treemap_subchart(fig)
    return fig

def prepare_contiguous_data(df, date_col, col):
    """
    Prepare data with None values for non-contiguous dates

    Args:
        df (pd.DataFrame): The input dataframe.
        date_col (str): The column name for the dates.
        col (str): The column name for the y-values.

    Returns:
        x_array, y_array (tuple): Modified x and
            y arrays with None values for gaps.
    """
    df_sorted = df.sort_values(by=date_col)

    x_array = []
    y_array = []
    for i in range(len(df_sorted)):
        x_array.append(df_sorted[date_col].iloc[i])
        y_array.append(df_sorted[col].iloc[i])

        # Check if next date is non-contiguous
        if i < len(df_sorted) - 1:
            current_date = df_sorted[date_col].iloc[i]
            next_date = df_sorted[date_col].iloc[i+1]
            time_diff = next_date - current_date
            if time_diff > pd.Timedelta(minutes=10):
                x_array.append(None)
                y_array.append(None)
    return x_array, y_array

def gen_level4_subchart(df, inverter):
    """Create the level4 subchart in the inverter treemap.

    Args:
        df (pandas.DataFrame): The output of the method
            `Databricks_Repository.get_inverter_performance_power_no_online_filter`.
        inverter (str): The name of the inverter of interest.

    Returns:
        fig (plotly.graph_objects.Figure): A Plotly Figure.
    """
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    date_col = "start_time_utc"
    was_there_secondary_axis = False
    for col in df.columns:
        first_ele = None
        try:
            first_ele = df[col].iloc[0]
        except IndexError:
            pass
        if first_ele is None or not isinstance(first_ele, (int, float)):
            continue
        secondary_y = False
        if "irradiance" in col.lower():
            secondary_y = True
            was_there_secondary_axis = True
        df_sorted = df.sort_values(by=date_col)

        x_array, y_array = prepare_contiguous_data(df_sorted, date_col, col)
        fig.add_trace(go.Scatter(
            x=x_array,
            y=y_array,
            mode="lines",
            name=col,
            hovertemplate=f"<b>{inverter}</b><br>" + col + ": %{y}<br>" + date_col + ": %{x}<extra></extra>",
        ), secondary_y=secondary_y)

    # style the figure
    if was_there_secondary_axis:
        fig.update_yaxes(title_text="Power (kW)", secondary_y=False)
        fig.update_yaxes(title_text="POA Irradiance (W/m²)", secondary_y=True)
    else:
        fig.update_yaxes(title_text="Power (kW)")
    fig.update_xaxes(title_text="Start Time")
    fig = style_treemap_subchart(fig)
    return fig
