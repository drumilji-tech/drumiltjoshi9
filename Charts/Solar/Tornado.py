"""Plotting and Helper Functions for the Tornado Section."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .Helpers import (
    extract_plant,
    extract_measurement,
    extract_power_conversion_station,
    extract_weather_station,
)
from Utils.ISightConstants import (
    DATABASE_METRIC_TRANSLATOR,
    METRIC_MEASURE_LOOKUP,
    METRIC_TOOLTIP_DECIMAL_ROUNDING,
    TORNADO_TOOLTIP_SYMBOL_MISSING,
    TORNADO_TOOLTIP_CODE_THIS_MISSING,
    TORNADO_TOOLTIP_CODE_ALL_MISSING,
)

def gen_clearsky_ratios_for_tooltip(raw_distance_data, all_clear_sky_ratios):
    """Prepare an in-sync array of clear sky percentages.

    Args:
        raw_distance_data (pd.Series):
        all_clear_sky_ratios (pd.DataFrame): This is the output of:
            `DatBricks_Repository.get_all_clear_sky_ratios`
    Returns:
        ordered_ratios (list): A list of strings of the form "a/b",
            representing the ratio of clear sky days to total days.
            They are ordered according to the order of plant names
            found in the index of `raw_distance_data`.
    """
    if all_clear_sky_ratios is None:
        return [TORNADO_TOOLTIP_CODE_ALL_MISSING for _ in raw_distance_data.index]

    index_plants = [extract_plant(index) for index in raw_distance_data.index]
    ordered_ratios = []
    for plant in index_plants:
        if len(all_clear_sky_ratios) <= 0:
            val = -111
        elif len(all_clear_sky_ratios[all_clear_sky_ratios["plant"] == plant]) <= 0:
            val = -333
        else:
            clear_sky_day_count = all_clear_sky_ratios[
                all_clear_sky_ratios["plant"] == plant
            ]["clear_sky_day_count"].values[0]
            total_days_count = all_clear_sky_ratios[
                all_clear_sky_ratios["plant"] == plant
            ]["total_days_count"].values[0]
            val = f"{int(clear_sky_day_count)}/{int(total_days_count)}"
        ordered_ratios.append(val)
    return ordered_ratios

def gen_budget_deviation_numbers_for_tooltip(
    budget_deviation_df,
    yaxis_label_arr,
    raw_distance_data,
):
    """Prepare an in-sync array of budget deviation vals for the tooltip."""
    if len(budget_deviation_df) > 0:
        dff_index = yaxis_label_arr.index.to_series()
        budget_deviation_df = budget_deviation_df.reindex(
            dff_index.values,
            fill_value=TORNADO_TOOLTIP_CODE_THIS_MISSING,
        )
        budget_deviation_series = budget_deviation_df["deviation"]
    else:
        budget_deviation_series = [TORNADO_TOOLTIP_CODE_ALL_MISSING for _ in raw_distance_data]
    return budget_deviation_series

def gen_recovery_numbers_for_tooltip(
    recovery_df,
    data,
    raw_distance_data,
):
    """Prepare an in-sync array of recovery vals for the tooltip."""
    if recovery_df is not None and len(data) > 0:
        new_cols_to_show = list(set(data.index))
        new_regex_cols = "|".join([f"({n.split('_')[0]})" for n in new_cols_to_show])
        dff = recovery_df.filter(regex=new_regex_cols)
        index_pre_underscore = raw_distance_data.index.str.replace(r'_.*$', '', regex=True)
        dff = dff.reindex(index_pre_underscore)
        dff = pd.to_numeric(dff, errors='coerce').fillna(0).astype(int)
        recovery_data = dff.values

        # TODO: move this assert into a test
        assert all(dff.index == index_pre_underscore)

        if len(recovery_data) != len(raw_distance_data):
            recovery_data = [TORNADO_TOOLTIP_SYMBOL_MISSING for _ in raw_distance_data]
    else:
        recovery_data = [TORNADO_TOOLTIP_CODE_ALL_MISSING for _ in data]
    return recovery_data

def style_horizontal_bar_chart(fig, metric):
    """Style a Plotly figure intended as a Tornado chart.
    
    Args:
        fig (plotly.graph_objects.Figure): A Plotly
            figure.
        metric (str): See `gen_horizontal_bar_chart` docstring.

    Returns:
        (plotly.graph_objects.Figure): Another Plotly figure.
    """
    fig.update_traces(hoverinfo="none", hovertemplate=None)
    xaxis_title = "Relative Deviation"
    if metric is not None:
        measure = ""
        try:
            measure = METRIC_MEASURE_LOOKUP[metric]
        except KeyError:
            pass
        if measure.lower() == "distance":
            sep = " "
        else:
            sep = " - "
        xaxis_title = f"{metric.title()}{sep}{measure}"
    fig.update_layout(
        dragmode="select",
        showlegend=False,
        template="plotly_dark",
        xaxis=dict(
            title=xaxis_title,
            zerolinewidth=2,
        ),
        yaxis=dict(
            title="Weather Station",
            zerolinewidth=2,
            automargin=True,
            autoshift=True,
        ),
        height=650,
    )
    return fig

def prune_metric_attributes(column, include_measurement=None):
    """Format a column metric attributes into a shorter label.

    This function takes a string like "ADB-BLK01-PCS002-WS1-BOM_eucl"
    and returns "ADB-002-WS1". These pruned labels are meant for
    display as axis lables in the weather station charts.

    Args:
        include_measurement (bool): Determines if the measurment
            from the tag is included in the formated label
    """
    if include_measurement is None:
        include_measurement = False

    plant = extract_plant(column)
    pcs = extract_power_conversion_station(column)
    ws = extract_weather_station(column)
    segments = [plant, pcs, ws]
    if include_measurement:
        meas = extract_measurement(column)
        segments.append(meas)

    if any([not s for s in segments]):
        return column
    return "-".join(segments)

def filter_data_by_metric(data_frame, metric):
    """Filter Tornado Data by a Metric.

    Args:
        data_frame (pd.DataFrame): The input dataset.
        metric (str): This is any of the keys
            of `DATABASE_METRIC_TRANSLATOR`.
            Example: "euclidean".
    Returns:
        (pd.DataFrame): The filtered
            dataframe.
    """
    translated_metric = DATABASE_METRIC_TRANSLATOR[metric]
    return data_frame.filter(regex=f"_{translated_metric}$")

def gen_horizontal_bar_chart(
    data,
    recovery_df=None,
    metric=None,
    color_by_pct_diff=None,
    budget_deviation_df=None,
    lost_revenue_df=None,
    all_clear_sky_ratios_df=None,
    only_clear_sky_days=None,
    base_color=None,
):
    """Generates just a chart agnostic to the data going inside.

    Args:
        data (pd.Series): A series with Weather Stations in the
            index, each pointing to some value. These values are
            supposed to come from precalculated metrics that we
            want to display.
        recovery_df (pd.Series): A pandas series containing the
            columns to plot. This object also contains the recovery
            values that appear in the tooltip when you hover your
            mouse over a data point.
        metric (str, optional): The metric determines what the
            lengths of the tornado bars are. If this parameter is
            set, the `data` is parsed and split, taking the metric-
            part to represent the horizontal bar lengths, and placing
            the non-metric- part into the tooltip.

            If `None`, no parsing is done, then all the data points
            from `data` are plotting in the chart as lines.
        color_by_pct_diff (bool): Determines if the data points are
            colored based on the corresponding percent difference from
            SolorAnywhere. This also places a colorbar in the plot.
            This param is optional and True by default.
        budget_deviation_df (pd.DataFrame): The budget deviation data.
        lost_revenue_df (pd.DataFrame): The lost revenue data.
        all_clear_sky_ratios_df (pd.DataFrame): ...
        only_clear_sky_days (bool): ...
        base_color (str): The base color of the Tornado bars.

    Returns:
        fig (plotly.Figure): A Plotly Figure ready for plotting.
    """
    if base_color is None:
        base_color = "#02BCF0"  # this is just the "southernpower-blue" color from our CSS

    if color_by_pct_diff is None:
        color_by_pct_diff = True
    if not isinstance(budget_deviation_df, pd.DataFrame):
        budget_deviation_df = pd.DataFrame()
    if not isinstance(lost_revenue_df, pd.DataFrame):
        lost_revenue_df = pd.DataFrame()
    if only_clear_sky_days is None:
        only_clear_sky_days = False

    # filter out columns outside recovery threshold
    if recovery_df is not None:
        cols_to_show = list(recovery_df.index)
        regex_cols = "|".join([f"({n})" for n in cols_to_show])
        if len(cols_to_show) <= 0:
            fig = go.Figure(data=[])
            fig = style_horizontal_bar_chart(
                fig=fig,
                metric=metric,
            )
            return fig
        else:
            data = data.filter(regex=regex_cols)

    # keep only clear sky days, if active in the UI 
    if only_clear_sky_days:
        plants_with_zero_ratio = all_clear_sky_ratios_df.loc[all_clear_sky_ratios_df['ratio'] == 0, 'plant'].values
        data = data[[index for index in data.index if not any(index.startswith(plant) for plant in plants_with_zero_ratio)]]

    # filter data by metric
    raw_distance_data = data
    if metric is not None:
        raw_distance_data = filter_data_by_metric(data_frame=data, metric=metric)

    # prepare the cleaned y-axis labels
    yaxis_label_arr = raw_distance_data.rename(index=lambda x: prune_metric_attributes(x))

    # Tooltips: prepare all numbers from metrics
    custom_data_arr = [raw_distance_data.index]
    abs_pct_diff_arr = [0 for _ in raw_distance_data]
    for key in DATABASE_METRIC_TRANSLATOR:
        dff = filter_data_by_metric(data_frame=data, metric=key)

        dff = pd.to_numeric(dff, errors="coerce")
        decimals = METRIC_TOOLTIP_DECIMAL_ROUNDING[key]
        if decimals > 0:
            dff = dff.astype(float, errors="ignore").round(decimals)
        else:
            dff = dff.astype(int, errors="ignore").round(decimals)

        # indicate that this metric is missing datapoints
        if len(dff) != len(raw_distance_data):
            dff = [TORNADO_TOOLTIP_SYMBOL_MISSING for _ in raw_distance_data]
        custom_data_arr.append(dff)

        # save the absolute percent diff. for the colorbar scale
        if key == "pct diff":
            try:
                dff = dff.abs()
            except AttributeError:
                dff = [abs(v) for v in dff]
            abs_pct_diff_arr = dff

    budget_deviation_series = gen_budget_deviation_numbers_for_tooltip(
        budget_deviation_df=budget_deviation_df,
        yaxis_label_arr=yaxis_label_arr,
        raw_distance_data=raw_distance_data,
    )
    custom_data_arr.append(budget_deviation_series)

    recovery_data = gen_recovery_numbers_for_tooltip(
        recovery_df=recovery_df,
        data=data,
        raw_distance_data=raw_distance_data,
    )
    custom_data_arr.append(recovery_data)

    clear_sky_vals = gen_clearsky_ratios_for_tooltip(
        raw_distance_data=raw_distance_data,
        all_clear_sky_ratios=all_clear_sky_ratios_df,
    )
    custom_data_arr.append(clear_sky_vals)

    lost_revenue_series = gen_budget_deviation_numbers_for_tooltip(
        budget_deviation_df=lost_revenue_df,
        yaxis_label_arr=yaxis_label_arr,
        raw_distance_data=raw_distance_data,
    )
    custom_data_arr.append(lost_revenue_series)

    customdata = np.stack(custom_data_arr, axis=-1)

    if color_by_pct_diff:
        color = abs_pct_diff_arr

        # safely set the min and max tick values
        try:
            min_tick_val = min(abs_pct_diff_arr)
        except ValueError:
            min_tick_val = 0  # this number is arbitrary
        try:
            max_tick_val = max(abs_pct_diff_arr)
        except ValueError:
            max_tick_val = 100  # this number is arbitrary
        tickvals = [min_tick_val, max_tick_val]

        ticktext = [f"{val}%" for val in tickvals]
        colorbar = dict(
            title="Pct Diff (%)",
            orientation="h",
            thickness=10,
            ticksuffix="%",
            tickvals=tickvals,
            ticktext=ticktext,
            y=-0.25,
        )
        showscale = True
    else:
        color = base_color
        colorbar = None
        showscale = False

    # create the trace of dots (colored by pct diff.)
    trace = go.Scatter(
        x=yaxis_label_arr,
        y=yaxis_label_arr.index,
        mode="markers",
        marker=dict(
            size=6,
            color=color,
            colorscale="thermal",
            showscale=showscale,
            colorbar=colorbar,
        ),
        showlegend=False,
        customdata=customdata,
    )

    # create the trace of horizontal lines connecting to the dots
    x_arr = []
    y_arr = []
    for idx, datum in zip(yaxis_label_arr.index, yaxis_label_arr):
        x_arr.extend([0, datum, None])
        y_arr.extend([idx, idx, None])
    line_trace = go.Scatter(
        mode="lines",
        x=x_arr,
        y=y_arr,
        marker=dict(color=base_color),
        line=dict(color=base_color),
        showlegend=False,
        hoverinfo="skip",
    )
    fig = go.Figure(data=[line_trace, trace])
    fig = style_horizontal_bar_chart(
        fig=fig,
        metric=metric,
    )
    return fig


def gen_recovery_chart(data):
    """Create a horizontal bar chart to display recovery values.
    
    Args:
        data (pd.Series): The recovery values, with the index
            representing the raw tag, and the values of the
            series being the recovery values, ranging from 0
            to 100 inclusive.

    Returns:
        fig (plotly.graph_objects.Figure): A Plotly figure.
    """
    names = data.rename(index=lambda x: prune_metric_attributes(x, include_measurement=True))
    trace = go.Bar(
        y=names.index,
        x=data,
        orientation="h",
        text=data.index,
        name="",
        textposition="none",
        hovertemplate="<b>%{text}</b><br>Recovery (%): %{x:.2f}",
        marker=dict(color="#007CB8"),
    )
    fig = go.Figure(
        data=[trace],
        layout=dict(),
    )
    fig.update_layout(
        template="plotly_dark",
        height=900,
        xaxis=dict(
            ticksuffix="%",
            showticksuffix="all",
            title="Recovery (%)",
            tickmode="auto",
        ),
    )
    return fig