"""A Colleciton of Plotting Functions."""

import re
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dateutil.relativedelta import relativedelta

from Charts.Hovertemplate import (
    append_units_and_round,
    gen_hovertemplate,
)
from Utils.ISightConstants import (
    DATABASE_METRIC_TRANSLATOR,
    REVERSE_DATABASE_METRIC_TRANSLATOR,
    METRIC_MEASURE_LOOKUP,
    METRIC_TOOLTIP_DECIMAL_ROUNDING,
    TORNADO_TOOLTIP_SYMBOL_MISSING,
    TORNADO_TOOLTIP_CODE_THIS_MISSING,
    SOLAR_DRILLED_DOWN_CHART_HEIGHT,
    MEASUREMENT_UNITS_LOOKUP,
    PI_TAG_REGEX_PATTERN_LOOKUP,
)
from Utils.Transformers import (
    filter_dates,
    filter_oem,
    get_project_data,
    remove_acknowledged_values,
    add_turbine_fault_column,
    filter_fault_codes,
)
from Utils.UiConstants import (
    FAULT_PULSE_PARETO_CHART_HEIGHT,
    PEBBLE_CHART_METRICS,
    PARETO_COLORS,
    BLUE_COLOR,
    FAULT_METRIC_LOOKUP,
    METRIC_UNITS,
    TURBINE_FAULT_DELIM,
    DESCRIPTION_CODE_DELIM,
    FAULT_METRIC_COLUMN_LOOKUP,
)


def default_chart(bgcolor=None):
    """An empty plotly figure with a grey background.

    This plot serves as an aesthetic empty chart that is meant
    to display in all chart spaces when the app is initially
    loading.

    This function should be set to the `figure` param of a
    `dcc.Graph` container to acheive this effect. Normally, if
    the `figure` param is not provided, a white background empty
    chart will be loaded up, but this creates a lot of visual
    noise in this app, which has a dark-mode palette.

    Args:
        bgcolor (str, optional): The background color of the chart.
            If not provided, it will auto be set to a grey color.
    Returns:
        (a plotly.graph_object.Figure)
    """
    if bgcolor is None:
        bgcolor = "#444444"
    fig = go.Figure(
        data=[go.Scatter(x=[0], y=[0], visible=False)],
        layout=dict(
            plot_bgcolor=bgcolor,
            paper_bgcolor=bgcolor,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        ),
    )
    return fig


def generate_pebble_chart(
    df_metric,
    metric,
    start,
    end,
    project=None,
    is_trip=None,
    oem=None,
    acknowledged_faults=None,
    selected_fault=None,
):
    """Plots a daily-aggregated Fault-Code metric.

    The purpose of the pebble chart is to show all Turbines and
    all Faults together in one space.

    Args:
        df_metric (pandas.DataFrame): This data_frame should be
            the output of the `load_pebble_daily_metric` helper
            function. See its docstring to learn more about
            shape and structure.
        metric (str): One of "downtime", "lost energy", or
            "lost revenue". This param specifies a type of column
            available in `df_metric`.
        start (Optional[datetime]): Start date of the time window
            to consider. Defaults to None.
        end (Optional[datetime]): End date of the time window to
            consider. Defaults to None.
        project (str): Filters the `data_frame` by a project name.
            An example project name is 'PDK-T005'. If "All", then
            no filtering is done.
        is_trip (bool): Determines if we filter our dataset by trip
            (True) or no trips (False). A "Trip" refers to an internal
            threshold that deems a Turbine in need of someone to
            literally visit the Turbine on the ground.
        oem (str): "OEM" stands for Original Equipment Manufacturer.
            This parameter filters the turbine by the OEM. If "All",
            then no filtering is done.
        acknowledged_faults (list): An array of "Code | Description" strings
            that come from the Fault Acknowledge Component.

    Returns:
        (plotly.express.scatter) A Plotly Scatter plot.
    """

    def filter_metric(dff, metric):
        """Filter out all the columns that don't contain `metric`."""
        fmt_metric = metric.replace(" ", "-").upper()
        dff = dff[dff.columns[dff.columns.str.contains(fmt_metric)]]
        return dff

    if project is None:
        project = "All"
    if is_trip is None:
        is_trip = False
    if oem is None:
        oem = "All"

    dff = df_metric
    dff = df_metric
    if project != "All":
        dff = get_project_data(dff, project, filter_columns=False)
    dff = filter_oem(data=dff, oem=oem)

    dff = dff.drop("Date", axis=1)
    dff = dff.rename(columns=FAULT_METRIC_COLUMN_LOOKUP)

    # Make sure we do not sum our string columns. This would lead
    # to Fault Descriptions consistning of the same string repeated
    # several times, making the text in the chart incomprehensive
    numeric_cols = dff.select_dtypes(include=["number"]).columns.tolist()
    agg_dict = {}
    for col in dff.columns:
        if col in ["Turbine", "FaultCode"]:
            continue
        elif col in numeric_cols:
            agg_dict[col] = "sum"
        else:
            agg_dict[col] = "first"
    combined_df = dff.groupby(["Turbine", "FaultCode"]).agg(agg_dict)

    combined_df = combined_df.reset_index()
    combined_df["Downtime"] = round(combined_df["Downtime"] / 3600, 1)
    combined_df[["Lost Energy", "Lost Revenue"]] = combined_df[
        ["Lost Energy", "Lost Revenue"]
    ].round(2)

    if isinstance(selected_fault, (list, tuple)) or isinstance(acknowledged_faults, (list, tuple)):
        acknowledge_array = [
            val.split(DESCRIPTION_CODE_DELIM)[0].strip() for val in acknowledged_faults
        ]
        filter_array = [
            val.split(DESCRIPTION_CODE_DELIM)[0].strip() for val in selected_fault
        ]
        combined_df = remove_acknowledged_values(
            df=combined_df,
            values=acknowledge_array,
            colname="FaultCode")

        combined_df = filter_fault_codes(
            df=combined_df,
            fault_codes=filter_array,
            colname="FaultCode")

    # make the title
    title_fmt = "%b %d, %Y"
    fmt_date_arr = []
    for date_str in [start, end]:
        fmt_date = date_str.split("T")[0]
        fmt_date = datetime.strptime(fmt_date, "%Y-%m-%d")
        fmt_date = fmt_date.strftime(title_fmt)
        fmt_date_arr.append(fmt_date)
    header = f"Fault Code Analysis, Sorted by {metric} ({fmt_date_arr[0]} to {fmt_date_arr[1]})"
    subtitle = f"Displaying {len(combined_df)} Fault Codes"
    title = "<br>".join([header, subtitle])

    # make the figure
    hover_data = ["Turbine", "FaultCode", "Description", "Count"] + PEBBLE_CHART_METRICS
    x = "Count"
    fig = px.scatter(
        data_frame=combined_df,
        x=x,
        y=metric,
        title=title,
        hover_data=hover_data,
    )
    hovertemplate = gen_hovertemplate(
        hover_data=hover_data,
        x="Count",
        y=metric,
    )
    fig.update_traces(hovertemplate=hovertemplate)
    fig.update_layout(
        template="plotly_dark",
        xaxis=dict(
            title="Total Fault Counts",
        ),
        yaxis=dict(
            title=metric,
        ),
    )
    return fig


def generate_pulse_pareto_chart(
    fault_metrics_df,
    fault_daily_metrics_df,
    start_date,
    end_date,
    metric,
    project,
    num_of_rows=None,
    turbine_arr=None,
    oem=None,
):
    """Creates the Pulse and Pareto chart for Fault Analysis.

    The Pulse and the Pareto chart sit side by side, and share
    the same yaxis labels. The yaxis labels are 'Turbine - Fault'
    pairs. For example, a yaxis label of "BTH-T093 - 1" indicates
    "BTH-T093" as the turbine and "1" as the fault code.

    The charts are sorted based on a `metric` from the UI, and the
    rows are sorted in descending order.

    Args:
        fault_metrics_df (pandas.DataFrame): This dataset should come from
            the output of the `load_fault_metrics` helper function.
        fault_daily_metrics_df (pandas.DataFrame): this dataframe comes from the output
            of `load_daily_fault_metrics` helper function.
        start_date (datetime): The start date of the chart.
        start_date (datetime): The end date of the chart.
        metric (str): One of "Downtime", "Lost Revenue", or "Lost Energy".
        project (str): A value that comes from the global project dropdown.
        num_of_rows (int, optional): The number of rows that both the pulse and
            the pareto chart have. If None, the number of rows will be driven
            by the underlying dataset and will not be capped.
        oem (str): "OEM" stands for Original Equipment Manufacturer.
            This parameter filters the turbine by the OEM. If "All",
            then no filtering is done.
    Returns:
        fig (plotly.graph_objects.Figure): A Plotly figure with two subplots.
    """

    def construct_title(
        start_date,
        end_date,
        metric,
        project,
        num_of_rows,
        turbine_arr,
        is_site,
        fault_duration,
    ):
        """Create an informative title for the chart."""
        title_fmt = "%b %d, %Y"
        start_title = start_date.strftime(title_fmt)
        end_title = end_date.strftime(title_fmt)

        if is_site:
            project_blurb = project
            if project == "All":
                project_blurb = "all projects"
            else:
                project_blurb = f"{project} Project"
            yaxis_dtype = "Turbine-Faults"
        else:
            project_blurb = ", ".join(turbine_arr)
            yaxis_dtype = "Faults"

        total_faults = len(fault_duration["TurbineFaultCode"])
        if num_of_rows == total_faults:
            callout = f"All {total_faults}"
        else:
            callout = f"Top {num_of_rows} of {total_faults}"
        return (
            f"{callout} "
            f"{yaxis_dtype} (by {metric}) "
            f"from {project_blurb} "
            f"({start_title} to {end_title})"
        )

    if oem is None:
        oem = "All"

    # figure out the array of turbines
    is_site = False
    turbine_daily_arr = turbine_arr
    if turbine_arr is None:
        is_site = True

        turbine_arr = fault_metrics_df["Turbine"].unique()
        turbine_daily_arr = fault_daily_metrics_df["Turbine"].tolist()

        if project != "All":
            column_name = "Turbine"
            project_data = get_project_data(
                data=fault_metrics_df,
                project=project,
                filter_columns=False,
                column_name=column_name,
            )

            filtered_daily_df = get_project_data(
                data=fault_daily_metrics_df,
                project=project,
                filter_columns=False,
                column_name=column_name,
            )

            turbine_arr = project_data[column_name].unique()

    # filter turbines outside the UI-selected 'oem'
    turbine_arr = pd.Series(turbine_arr)
    turbine_arr = filter_oem(data=turbine_arr, oem=oem)
    turbine_arr = turbine_arr.tolist()
    turbine_daily_arr = turbine_arr

    # adjust the end date so that it encompasses all minutes and seconds of the end
    # date passed allowing to match tree map and pebble
    adj_end_date = end_date + relativedelta(hours=23, minutes=59, seconds=59)

    filtered_df = fault_metrics_df[
        (fault_metrics_df["Turbine"].isin(turbine_arr))
        & (fault_metrics_df["AdjustedStartDateTime"] >= start_date)
        & (fault_metrics_df["AdjustedStartDateTime"] < adj_end_date)
    ]

    filtered_daily_df = fault_daily_metrics_df
    filtered_daily_df = filtered_daily_df[
        filtered_daily_df["Turbine"].isin(turbine_daily_arr)
    ]
    filtered_df = add_turbine_fault_column(filtered_df)
    filtered_daily_df = add_turbine_fault_column(filtered_daily_df)

    metric_col = FAULT_METRIC_LOOKUP[metric]
    fault_duration = (
        filtered_daily_df.groupby(["TurbineFaultCode", "FaultCode", "Description"])[
            metric_col
        ]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )

    # set up the subplot
    pulse_title = "Fault Timeline"
    pareto_texttemplate = append_units_and_round(var="x", metric=metric)
    pareto_title = f"Total {metric} ({METRIC_UNITS[metric]})"
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=False,
        column_widths=[0.7, 0.3],
        horizontal_spacing=0.05,
        subplot_titles=(pulse_title, pareto_title),
    )

    if num_of_rows is None:
        num_of_rows = len(fault_duration["TurbineFaultCode"])

    yaxis_vals = []
    for turbine_fault_pair in fault_duration["TurbineFaultCode"][:num_of_rows]:
        subset_df = filtered_df[filtered_df["TurbineFaultCode"] == turbine_fault_pair]

        yaxis_vals.append(turbine_fault_pair)
        x_arr = list(subset_df["StartDateTime"])
        y_arr = list(subset_df["TurbineFaultCode"])
        text_arr = list(subset_df["Description"])

        opacity = 0.9
        hoverinfo = "all"
        hovertemplate = "Turbine-Fault: %{y}<br>Description: %{text}<br>Start Time: %{x}<extra></extra>"
        if len(x_arr) <= 0 and len(y_arr) <= 0:
            x_arr = [adj_end_date]
            y_arr = [turbine_fault_pair]
            opacity = 0
            hoverinfo = "skip"
            hovertemplate = None
        pulse_trace = go.Scattergl(
            x=x_arr,
            y=y_arr,
            mode="markers",
            text=text_arr,
            opacity=opacity,
            marker=dict(
                symbol="line-ns-open",
                size=7,
                color=PARETO_COLORS["normal"],
            ),
            name=str(turbine_fault_pair),
            hoverinfo=hoverinfo,
            hovertemplate=hovertemplate,
            showlegend=False,
        )
        fig.add_trace(
            pulse_trace,
            row=1,
            col=1,
        )

    xaxis_vals = []
    description_vals = []
    for y in yaxis_vals:
        x = fault_duration[fault_duration["TurbineFaultCode"] == y][metric_col].tolist()
        if metric == "Downtime":
            x = [i / 3600 for i in x]
        xaxis_vals.extend(x)

        # construct an array of descriptions
        code = y.split(TURBINE_FAULT_DELIM)[-1]
        code = int(code)
        d = fault_duration[fault_duration["FaultCode"] == code]["Description"]
        d_val = d.values[0]
        description_vals.append(d_val)

    hovertemplate = "".join(
        [
            "Turbine Fault: %{y}<br>",
            "Description: %{text}<br>",
            metric,
            ": ",
            pareto_texttemplate,
            "<extra></extra>",
        ]
    )
    pareto_trace = go.Bar(
        x=xaxis_vals,
        y=yaxis_vals,
        textposition="inside",
        text=description_vals,
        texttemplate=pareto_texttemplate,
        orientation="h",
        marker=dict(color=PARETO_COLORS["highlight"]),
        name="pareto-trace",
        hovertemplate=hovertemplate,
        showlegend=False,
    )
    fig.add_trace(
        pareto_trace,
        row=1,
        col=2,
    )
    fig.update_layout(
        template="plotly_dark",
        title=construct_title(
            start_date=start_date,
            end_date=end_date,
            metric=metric,
            project=project,
            num_of_rows=num_of_rows,
            turbine_arr=turbine_arr,
            is_site=is_site,
            fault_duration=fault_duration,
        ),
        xaxis_title="Time",
        yaxis=dict(dtick=1),
        yaxis_tickfont_color=PARETO_COLORS["normal"],
        xaxis2_title=pareto_title.replace("Total", "").strip(),
        height=FAULT_PULSE_PARETO_CHART_HEIGHT,
        hovermode="y unified",
    )
    fig.update_yaxes(autorange="reversed")
    return fig
