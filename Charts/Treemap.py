## My code changes for treemap.py

"""Making Treemaps for the App."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import mode

from Charts.Hovertemplate import (
    append_units_and_round,
    join_hover_pair,
    join_hover_lines,
    gen_hovertemplate,
    TREEMAP_HOVERLABEL,
)
from Utils.Constants import (
    DEFAULT_PARSE_FUNCS,
    KEY_TO_NAME,
    TRANSFORMER_COMPONENTS
)
from Utils.Transformers import (
    get_component_type,
    get_project_component,
    get_project_data,
    get_turbine,
    filter_dates,
    filter_oem,
    remove_acknowledged_values,
    filter_fault_codes,
)
from Utils.UiConstants import (
    ALL_FAULT_CHART_METRICS,
    FAULT_METRIC_COLUMN_LOOKUP,
    DESCRIPTION_CODE_DELIM,
    PERFORMANCE_METRICS,
    PERFORMANCE_METRICS_LABEL_LOOKUP,
    DEFAULT_CHART_HEIGHT,
)
from Utils.Enums import ComponentTypes

MARGIN_RIGHT = 120

# See the Plotly Docs for valid colorscale names
# https://plotly.com/python/builtin-colorscales/#builtin-sequential-color-scales
COMP_TEMP_COLORSCALE = "Inferno"
POWER_PERF_COLORSCALE = "Viridis"
FAULT_COLORSCALE = "Inferno"


def remove_columns_with_missing_values(df, start=None, end=None):
    """
    Removes columns from the DataFrame which do not have the same number of valid (non-missing) values
    as the mode of valid value counts within the specified range.

    Parameters:
    df (pd.DataFrame): The DataFrame to process.
    start (str, optional): The start date as a string. If None, uses the first index.
    end (str, optional): The end date as a string. If None, uses the last index.

    Returns:
    pd.DataFrame: A new DataFrame with the specified columns removed.
    """
    if start is None:
        start = df.index[0]
    if end is None:
        end = df.index[-1]

    # Ensuring start and end are in the index
    if start not in df.index or end not in df.index:
        raise ValueError("Start or end date not found in DataFrame index.")

    # Get the range of dates
    date_range = df.loc[start:end]

    # Count the valid (non-missing) values for each column
    valid_counts = date_range.notnull().sum()

    # Find the mode of the valid counts
    valid_counts_mode = mode(valid_counts)[0][0]

    # Find columns that have a number of valid values equal to the mode
    cols_to_keep = valid_counts[valid_counts == valid_counts_mode].index

    # Keep only those columns
    df_cleaned = df.loc[:, cols_to_keep]

    return df_cleaned


def remove_cols_pp_treemap(treemap_data_simple_eff, sort_by):
    """Remove the columns that are not associated with the given metric.

    Args:
        treemap_data_simple_eff (pd.DataFrame): The simple efficiency
            dataset.
        sort_by (str): One of the values from the `PERFORMANCE_METRICS` constant.
    Returns:
        (pd.DataFrame): A dataframe with the same format as the input.
    """

    # remove the leading dash "-"
    metric = sort_by[1:]

    cols = [
        x
        for x in treemap_data_simple_eff.columns
        if metric == DEFAULT_PARSE_FUNCS["component_type_func"](x)
    ]
    treemap_data_simple_eff = treemap_data_simple_eff[cols]
    return treemap_data_simple_eff


def aggregate_pp_treemap_data(
        treemap_data_simple_eff,
        start=None,
        end=None,
        component_type=None,
        project=None,
        overperforming="underperforming",
        sort_by=None,
):
    """Aggregate the power performance treemap data by sum so we can easily plot it.

    Args:
        treemap_data_simple_eff (pandas.DataFrame): This is the relevant dataset.
        start (datetime|optional): Start date of the time window to consider. If start
            is not provided, the start date will be the first date in the dataset.
        end (datetime|optional): End date of the time window to consider. If
            end is not provided, the end date will be the last date in the dataset.
        component_type (str): String representing a specific component type to
            filter by. If you pass in "All", then all components will be included.
        project (str): String representing a specific project to filter by.
        overperforming (str): One of "underperforming" or "overperforming". This param
            controls the values that get filtered through the dataset, as well as if
            we reverse the colorscale or not.
        sort_by (str): One of the values from the `PERFORMANCE_METRICS` constant.

    Returns:
        (pd.DataFrame): The curated dataset ready for plotting.
    """
    treemap_data_simple_eff = remove_cols_pp_treemap(
        treemap_data_simple_eff=treemap_data_simple_eff, sort_by=sort_by
    )

    if start is None:
        start = treemap_data_simple_eff.index[0]
    if end is None:
        end = treemap_data_simple_eff.index[-1]

    # treemap_data_simple_eff = remove_columns_with_missing_values(treemap_data_simple_eff, start=start, end=end)

    treemap_data = sum_cols_pp_treemap(
        treemap_data_simple_eff=treemap_data_simple_eff,
        sort_by=sort_by,
        overperforming=overperforming,
    )
    treemap_data = treemap_data.round(2)

    treemap_data = treemap_data.to_frame().reset_index()
    treemap_data.columns = ["Turbine", "Severity"]

    treemap_data["TurbineRaw"] = treemap_data["Turbine"]
    treemap_data["Turbine"] = treemap_data["Turbine"].apply(
        lambda x: f"{get_turbine(x)}-{KEY_TO_NAME[get_component_type(x)]}"
    )

    if project != "All":
        treemap_data = get_project_data(treemap_data, project)

    treemap_data = treemap_data.sort_values(by="Severity", ascending=False).head(25)

    return treemap_data


def sum_cols_pp_treemap(
        treemap_data_simple_eff, sort_by, overperforming, start=None, end=None
):
    """Intelligently aggregate the column in question.

    Args:
        See `aggregate_pp_treemap_data` as it contains the same params.

    Returns:
        (pd.DataFrame): The aggregated and summed up dataframe.
    """
    if start is None:
        start = treemap_data_simple_eff.index[0]
    if end is None:
        end = treemap_data_simple_eff.index[-1]

    if sort_by == "-LOST-REVENUE":
        if overperforming == "overperforming":
            treemap_data = treemap_data_simple_eff.loc[
                           :, treemap_data_simple_eff.loc[start:end].sum() >= 0
                           ]
        else:
            treemap_data = (
                    treemap_data_simple_eff.loc[
                    :, treemap_data_simple_eff.loc[start:end].sum() < 0
                    ]
                    * -1
            )
    elif sort_by == "-LOST-ENERGY":
        if overperforming == "overperforming":
            treemap_data = treemap_data_simple_eff.loc[
                           :, treemap_data_simple_eff.loc[start:end].sum() >= 0
                           ]
        else:
            treemap_data = (
                    treemap_data_simple_eff.loc[
                    :, treemap_data_simple_eff.loc[start:end].sum() < 0
                    ]
                    * -1
            )

    elif sort_by == "-SEVERITY":
        if overperforming == "overperforming":
            treemap_data = treemap_data_simple_eff.loc[
                           :, treemap_data_simple_eff.loc[start:end].sum() > 0
                           ].fillna(0)

        else:
            treemap_data = (
                    treemap_data_simple_eff.loc[
                    :, treemap_data_simple_eff.loc[start:end].sum() <= 0
                    ].fillna(0)
                    * -1
            )
    treemap_data = treemap_data.loc[start:end].sum()
    return treemap_data


def generate_power_performance_treemap_databricks(
    data_frame,
    under_over_perform,
    sort_by,
):
    """Generate the Power Performance Treemap Chart."""
    if sort_by == "-LOST-REVENUE":
        severity_colname = "lost_revenue"
    elif sort_by == "-LOST-ENERGY":
        severity_colname = "lost_energy"
    elif sort_by == "-SEVERITY":
        severity_colname = "daily_relative_deviation"

    data_frame["Severity"] = data_frame[severity_colname]

    # Ensure that our severity values are positive so the Plotly Treemap works as expected
    if(len(data_frame) > 0 and data_frame["Severity"].iloc[0] < 0):
        data_frame["Severity"] = data_frame["Severity"] * -1

    # Grab an extreame value for the Colorbar
    try:
        max_severity = data_frame["Severity"].max()
    except:
        max_severity = 10

    hover_data = ["lost_revenue", "lost_energy", "daily_relative_deviation"]
    color_continuous_scale = POWER_PERF_COLORSCALE
    INVERTER_PERFORMANCE_COLORSCALE = px.colors.diverging.Fall
    INVERTER_PERFORMANCE_COLOR_OVERPERFORMING = INVERTER_PERFORMANCE_COLORSCALE[0]
    INVERTER_PERFORMANCE_COLOR_UNDERPERFORMING = INVERTER_PERFORMANCE_COLORSCALE[-1]
    if (
        under_over_perform == "underperforming"
    ):
        color_continuous_scale =  [[0, "rgb(255,255,255)"], [1, INVERTER_PERFORMANCE_COLOR_UNDERPERFORMING]]
    else:
        color_continuous_scale =  [[0, "rgb(255,255,255)"], [1, INVERTER_PERFORMANCE_COLOR_OVERPERFORMING]]
    as_icicle = True

    tooltip_footer = "NB. A negative number for a 'Lost' metric means there was a 'Gain'."
    hovertemplate = (
        "<b>Turbine</b>: %{label}<br>",
        "<b>Lost Revenue</b>: " + append_units_and_round(var="customdata[0]", metric="Lost Revenue") + "<br>",
        "<b>Lost Energy</b>: %{customdata[1]:.0f} MWh<br>",
        "<b>Relative Deviation</b>: %{customdata[2]:.0f}<br>",
        "<br>",
        tooltip_footer,
        "<extra></extra>",
    )
    hovertemplate = "".join(hovertemplate)
    treemap = construct_styled_treemap(
        treemap_data=data_frame,
        color_continuous_scale=color_continuous_scale,
        max_severity=max_severity,
        hovertemplate=hovertemplate,
        hoverdata=hover_data,
        as_icicle=as_icicle,
        line_break_char="-",
    )
    return treemap



def generate_power_performance_treemap(
        treemap_data_simple_eff,
        start=None,
        end=None,
        component_type=None,
        project=None,
        overperforming="underperforming",
        acknowledged_pp_turbines=None,
        sort_by="-LOST-REVENUE",
):
    """
    Generates a power performance treemap.

    Args:
        treemap_data_simple_eff (pandas.DataFrame): This is the relevant dataset.
        start (datetime|optional): Start date of the time window to consider. If start
            is not provided, the start date will be the first date in the dataset.
        end (datetime|optional): End date of the time window to consider. If
            end is not provided, the end date will be the last date in the dataset.
        component_type (str): String representing a specific component type to
            filter by. If you pass in "All", then all components will be included.
        project (str): String representing a specific project to filter by.
        overperforming (str): One of "underperforming" or "overperforming". This param
            controls the values that get filtered through the dataset, as well as if
            we reverse the colorscale or not.
        acknowledged_pp_turbines (list|tuple of str): An array of turbine-code
            labels that are not meant to show up in the final treemap.
        sort_by (str): One of the values of `PERFORMANCE_METRICS`. This param controls
            how the data is sorted in the treemap.

    Returns:
        plotly.graph_objects.Figure: A Plotly Treemap visualization.
    """

    def _join_all_metrics(df, start, end, sort_by, overperforming):
        """Ensure the dataset contains all metrics to display in the hover.

        This function adds 3 more columns to the already-sorted input dataset.
        Each of these columns contain the values of each metric for the turbines
        in the original dataset.

        Since the power performance treemap will already be sorted for one metric
        in descending order, we have to search the original `treemap_data_simple_eff`
        dataset to filter on dates, over or underperforming, and then finally
        sum up the values and prepare to join.
        """
        names = df["TurbineName"]
        for other_sort in PERFORMANCE_METRICS:
            simple_eff_copy = treemap_data_simple_eff.copy()
            simple_eff_copy = remove_cols_pp_treemap(
                treemap_data_simple_eff=simple_eff_copy, sort_by=other_sort
            )

            other_cols = ["".join([n, other_sort]) for n in names]
            simple_eff_copy = simple_eff_copy[other_cols]
            simple_eff_copy.columns = simple_eff_copy.columns.str.replace(
                other_sort, ""
            )
            simple_eff_copy = filter_dates(simple_eff_copy, start, end, is_index=True)

            dff_sum = sum_cols_pp_treemap(
                treemap_data_simple_eff=simple_eff_copy,
                sort_by=other_sort,
                overperforming=overperforming,
                start=start,
                end=end,
            )
            simple_eff_copy = pd.DataFrame(dff_sum, columns=[other_sort])
            df = df.join(simple_eff_copy, on="TurbineName")
        return df

    def _gen_pp_treemap_hovertemplate(hover_data):
        """Return the curated hovertemplate."""
        lines = [
            join_hover_pair(
                label="Turbine",
                value=append_units_and_round(var="label", metric="Turbine"),
            )
        ]
        for index, datum in enumerate(hover_data):
            label = PERFORMANCE_METRICS_LABEL_LOOKUP[datum]
            lines.append(
                join_hover_pair(
                    label=label,
                    value=append_units_and_round(
                        var=f"customdata[{index}]", metric=label
                    ),
                )
            )
        hovertemplate = join_hover_lines(lines)
        return hovertemplate

    treemap_data = aggregate_pp_treemap_data(
        treemap_data_simple_eff=treemap_data_simple_eff,
        start=start,
        end=end,
        component_type=component_type,
        project=project,
        overperforming=overperforming,
        sort_by=sort_by,
    )

    max_severity = treemap_data["Severity"].max()

    # reverse the colorscale when toggling between over/under-performing
    if overperforming == "overperforming":
        color_continuous_scale = POWER_PERF_COLORSCALE
    else:
        color_continuous_scale = "".join([POWER_PERF_COLORSCALE, "_r"])

    # remove acknowledged turbines before plotting dataset
    filtered_data = treemap_data
    if len(acknowledged_pp_turbines) > 0:
        regex_turbines = "|".join([f"(?:{n})" for n in acknowledged_pp_turbines])
        filtered_data = treemap_data[~treemap_data.Turbine.str.contains(regex_turbines)]

    filtered_data["TurbineName"] = filtered_data["TurbineRaw"].str.replace(sort_by, "")
    filtered_data = _join_all_metrics(
        df=filtered_data,
        start=start,
        end=end,
        sort_by=sort_by,
        overperforming=overperforming,
    )
    filtered_data.fillna(value=0, inplace=True)

    hover_data = PERFORMANCE_METRICS
    treemap = construct_styled_treemap(
        treemap_data=filtered_data,
        color_continuous_scale=color_continuous_scale,
        max_severity=max_severity,
        hovertemplate=None,
        hoverdata=hover_data,
    )
    hovertemplate = _gen_pp_treemap_hovertemplate(hover_data)
    treemap.update_traces(hovertemplate=hovertemplate)
    return treemap

def gen_comp_temp_treemap_databricks(df):
    """Construct the component temperature treemap.
    
    Args:
        df (pandas.DataFrame): The data coming from the
            get_wind_component_temperature_data
            method for the Databricks_Repository.
    Returns:
        (plotly.graph_objects.Figure): A Plotly chart.
    """
    df['element_component'] = df['element_name'] + '-' + df['isight_attribute_name']
 
    performance_df = df.groupby('element_component')['daily_relative_deviation'].sum().reset_index()

    # We grab the most positive relative deviation components to see what's 'running hot'
    performance_df.sort_values('daily_relative_deviation', ascending=False, inplace=True)
    worst_performers = performance_df.head(25)
    worst_performers = worst_performers.rename(columns={
        "element_component": "Turbine",
        "daily_relative_deviation": "Severity",
    })
    treemap = construct_styled_treemap(
        treemap_data=worst_performers,
        color_continuous_scale=COMP_TEMP_COLORSCALE,
        max_severity=max(worst_performers["Severity"]),
        hovertemplate=None,
    )
    return treemap

def gen_comp_temp_scatterplot(data):
    """Generate a Scatterplot Chart for Component Temperature.

    Args:
        data (pandas.dataframe): The data that comes from the
            get_wind_component_temperature_data method of the
            Datatbricks_Repository class.

    Returns:
        fig (plotly.graph_objects.Figure): A scatterplot chart.
    """
    data["diff_from_park"] = data["component_avg_temp"] - data["park_avg_temp"]

    # Encode absolute severity visually as larger markers in the plot
    data["abs_comp_sev"] = data["component_severity"].abs()
    data["size"] = data["abs_comp_sev"]
    data["size"].fillna(0, inplace=True)

    data = data.sort_values("isight_attribute_name")

    num_of_components = len(data)
    fig = px.scatter(
        data,
        x="diff_from_park",
        y="component_severity",
        color="isight_attribute_name",
        size="size",
        size_max=30,
        height=400,
        hover_data={
            "element_name": True,
            "isight_attribute_name": True,
            "diff_from_park": True,
            "component_avg_temp": True,
            "park_avg_temp": True,
            "component_severity" : True,
        },
        labels={
            "element_name": "Turbine",
            "isight_attribute_name": "Component",
            "diff_from_park": "Temp Deviation from Park Avg",
            "component_avg_temp": "Temp",
            "park_avg_temp": "Park Average Temp",
            "component_severity" : "Severity",
        },
    )
    fig.update_traces(hoverinfo="none", hovertemplate=None)

    try:
        min_severity = min(data["component_severity"])
    except ValueError:
        min_severity = -1
    try:
        max_severity = max(data["component_severity"])
    except ValueError:
        max_severity = 1

    if min_severity > 0 and max_severity > 0:
        min_severity = 0
    elif min_severity < 0 and max_severity < 0:
        max_severity = 0

    margin = 0.3 * max(abs(max_severity), abs(min_severity))
    min_severity -= margin
    max_severity += margin

    fig.update_layout(
        template="plotly_dark",
        legend={"itemclick": "toggleothers"},
        title=f"Showing {num_of_components} Components",
        yaxis={
            "title": {"text": "Severity", "font": {"size": 16}},
            "categoryorder": "total ascending",
            "showgrid": False,
            "showline": True,
            "tickmode": "array",
            "tickvals": [0],
            "range": [min_severity, max_severity],
            "linecolor": "#EEE",
            "zerolinecolor": "#EEE",
            "zerolinewidth": 2,
        },
        xaxis={
            "title": {"text": "Temp. Deviation from Components' Park Average (Δ°C)", "font": {"size": 16}},
            "ticksuffix": "°C",
            "showgrid": True,
            "showline": False,
            "zerolinecolor": "#555",
            "zerolinewidth": 4,
        },
    )
    return fig

def generate_comp_temp_treemap(
        treemap_data_from_file, start=None, end=None, component_type=None, project=None
):
    """
    Generates a treemap plot using the data from Wind Farm object.

    Args:
        treemap_data_from_file (pd.DataFrame): This is the relevant dataset.
        start (Optional[datetime]): Start date of the time window to consider. Defaults to None.
        end (Optional[datetime]): End date of the time window to consider. Defaults to None.
        component_type (Optional[str]): String representing a specific component type to filter by.
    Defaults to None.

    Returns:
    plotly.graph_objs._figure.Figure: A treemap plot showing the severity of issues in each turbine/component.
    """
    if start is None:
        start = treemap_data_from_file.index[0]
    if end is None:
        end = treemap_data_from_file.index[-1]

    mean_col_map = treemap_data_from_file.columns.str.contains(
        "_mean"
    ) & ~treemap_data_from_file.columns.str.contains(
        "|".join(["-DIR", "-YAW", "-LOST"])
    )

    # print('tm 398', start, end, treemap_data_from_file.loc[start:end, ~mean_col_map].copy())
    treemap_data = treemap_data_from_file.loc[start:end, ~mean_col_map].copy().sum()

    treemap_data = treemap_data.to_frame().reset_index()
    treemap_data.columns = ["Turbine", "Severity"]
    treemap_data["TurbineRaw"] = treemap_data["Turbine"]

    mean_data = treemap_data_from_file.loc[start:end, mean_col_map].copy().mean()
    mean_data.index = mean_data.index.str.replace("_mean", "")
    mean_data = mean_data.to_frame().reset_index()
    mean_data.columns = ["Turbine", "Mean"]

    project_component_pairs = mean_data["Turbine"].map(get_project_component)
    project_component_pairs = list(set(project_component_pairs))

    park_average_dict = {}
    for pc in project_component_pairs:
        matching_cols = [
            col for col in mean_data["Turbine"] if get_project_component(col) == pc
        ]
        park_average_dict[pc] = mean_data.loc[
            mean_data["Turbine"].isin(matching_cols), "Mean"
        ].mean()

    park_average_series = pd.Series(index=mean_data["Turbine"])

    for col in park_average_series.index:
        pc = get_project_component(col)
        park_average_series[col] = park_average_dict[pc]

    park_avg_data = park_average_series.to_frame().reset_index()
    park_avg_data.columns = ["Turbine", "Park Avg"]

    treemap_data = pd.merge(
        treemap_data, mean_data[["Turbine", "Mean"]], on="Turbine", how="left"
    )

    treemap_data = pd.merge(treemap_data, park_avg_data, on="Turbine", how="left")

    treemap_data["Turbine"] = treemap_data["Turbine"].apply(
        lambda x: None if any(
            component in f"{get_turbine(x)}-{KEY_TO_NAME.get(get_component_type(x), '')}" for component in
            TRANSFORMER_COMPONENTS)
        else f"{get_turbine(x)}-{KEY_TO_NAME.get(get_component_type(x), '')}"
    )
    treemap_data = treemap_data[treemap_data["Turbine"].notna()]

    if component_type != "All":
        treemap_data = treemap_data[
            treemap_data["Turbine"].str.contains(component_type)
        ]

    if project != "All":
        treemap_data = get_project_data(treemap_data, project)

    treemap_data = treemap_data.sort_values(by="Severity", ascending=False).head(25)

    # Scale the severity values to range [0, 1]
    max_severity = treemap_data["Severity"].max()

    treemap_data = treemap_data[treemap_data["Severity"] > 0].dropna()
    hovertemplate = (
        "<b>Turbine</b>: %{label}<br>"
        "<b>Mean Temperature</b>: %{customdata[0]:.0f}°C<br>"
        "<b>Park Avg Temperature</b>: %{customdata[1]:.0f}°C"
        "<extra></extra>"
    )
    hoverdata = ["Mean", "Park Avg"]
    treemap = construct_styled_treemap(
        treemap_data=treemap_data,
        color_continuous_scale=COMP_TEMP_COLORSCALE,
        max_severity=max_severity,
        hovertemplate=hovertemplate,
        hoverdata=hoverdata,
    )
    return treemap


def generate_fault_treemap(
        df_metric,
        metric,
        start,
        end,
        project=None,
        is_trip=None,
        oem=None,
        acknowledged_faults=None,
        selected_fault=None
):
    """Plots a Treemap displaying some Fault metric for each Turbine/Fault Code.

    Args:
        df_metric (pandas.DataFrame): A dataframe that has a
            pandas.DateTime index (where each row is for a day).
        metric (str): One of "downtime", "lost energy", "lost revenue",
            or "count". This param specifies a type of column available
            in `df_metric`.
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
        (plotly.express.scatter) A Plotly Treemap plot.
    """

    def make_title(start, end, metric):
        """Generate title for the chart."""
        start_title = start.strftime("%b %d, %Y")
        end_title = end.strftime("%b %d, %Y")
        title = f"Fault Code Analysis {metric} ({start_title} to {end_title})"
        return title

    if project is None:
        project = "All"
    if is_trip is None:
        is_trip = False
    if oem is None:
        oem = "All"

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
    treemap_df = dff.groupby(["Turbine", "FaultCode"]).agg(agg_dict)

    treemap_df = treemap_df.reset_index()
    if isinstance(selected_fault, (list, tuple)) or isinstance(acknowledged_faults, (list, tuple)):
        acknowledge_array = [
            val.split(DESCRIPTION_CODE_DELIM)[0].strip() for val in acknowledged_faults
        ]
        filter_array = [
            val.split(DESCRIPTION_CODE_DELIM)[0].strip() for val in selected_fault
        ]
        treemap_df = remove_acknowledged_values(
            df=treemap_df,
            values=acknowledge_array,
            colname="FaultCode")

        treemap_df = filter_fault_codes(
            df=treemap_df,
            fault_codes=filter_array,
            colname="FaultCode")

    treemap_df["Downtime"] = round(treemap_df["Downtime"].div(3600), 1)
    treemap_df[["Lost Energy", "Lost Revenue"]] = treemap_df[
        ["Lost Energy", "Lost Revenue"]
    ].round(2)

    treemap_df["TurbineFaultDescription"] = (
        treemap_df["Turbine"] + "<br>" + treemap_df["Description"]
    )
    treemap_df = (
        treemap_df.sort_values(metric, ascending=False).head(25).drop_duplicates()
    )

    hover_data = ["Turbine", "Description", "FaultCode"] + ALL_FAULT_CHART_METRICS
    hovertemplate = gen_hovertemplate(
        hover_data=hover_data,
        x=None,
        y=None,
    )
    treemap = px.treemap(
        treemap_df,
        names="TurbineFaultDescription",
        parents=["" for _ in range(len(treemap_df))],
        values=metric,
        color_continuous_scale=FAULT_COLORSCALE,
        color=metric,
        template="plotly_dark",
        title=make_title(start, end, metric),
        hover_data=hover_data,
    )
    treemap.update_traces(
        pathbar=dict(visible=False),
        marker_cornerradius=4,
        hovertemplate=hovertemplate,
        insidetextfont_size=20,
        selector=dict(type="treemap"),
    )
    treemap.update_layout(
        height=DEFAULT_CHART_HEIGHT + 100,
        uniformtext=dict(minsize=22),
        margin=dict(
            autoexpand=True,
            r=40,
            l=40,
            b=20,
            t=70,
        ),
    )
    return treemap


def construct_styled_treemap(
        treemap_data,
        color_continuous_scale,
        max_severity,
        hovertemplate=None,
        hoverdata=None,
        as_icicle=None,
        line_break_char=None,
):
    """Take prepared data and put together a Plotly Treemap.

    Args:
        treemap_data (pd.DataFrame): The curated dataset that
            contains Turbines and Severity data ready for plotting.
        color_continuous_scale (list): A Plotly parameter of the
            `plotly.express.treemap` method. Run `help(px.treemap)`
            to learn more about the Plotly Express treemap parameters.
        max_severity (int): The computed maximum severity coming from the dataset.
        hovertemplate (str, optional): ex--> "Turbine: %{label}<br>Mean Temperature: %{customdata[0]:.0f}°C<br>"
        hoverdata (list of str): column names to use for hover data ordered according to the
            hovertemplate
        as_icicle (bool, Optional): Determines if the chart is drawn as
            an Icicle plot (True), or a Treemap (False). Defaults to False.
        line_break_char (str, Optional): Specify the line break to split the
            plant and turbine name in the hovertemplate. Defaults to "<br>".
    Returns:
        (A `plotly.graph_objects.Figure` chart)
    """
    if as_icicle is None:
        as_icicle = False


    def _split_text(name, line_break_char=None):
        """Separate the project and component substring by a line break."""
        if line_break_char is None:
            line_break_char = "<br>"

        delim = "-"
        res = name.split(delim)
        project = f"{delim}".join(res[:-1])

        if res[-1] == "Lost_Revenue":
            component = "Revenue Delta"
        elif res[-1] == "Lost_Energy":
            component = "Lost Energy"
        elif res[-1] == "Severity":
            component = "Severity"
        else:
            component = res[-1]
        return f"{project}{line_break_char}{component}"

    turbine_arr = treemap_data["Turbine"].tolist()
    names = [_split_text(name, line_break_char=line_break_char) for name in turbine_arr]
    parents = ["" for _ in turbine_arr]
    values = treemap_data["Severity"].tolist()
    color = treemap_data["Severity"].tolist()

    if as_icicle:
        treemap = px.icicle(
            treemap_data,
            names=names,
            parents=parents,
            values=values,
            color_continuous_scale=color_continuous_scale,
            range_color=[0, max_severity],
            color=color,
            template="plotly_dark",
            hover_data=hoverdata,
        )
        treemap.update_traces(
            tiling = dict(
                orientation="v",
            )
        )
        treemap.update_layout(height=200)
    else:
        treemap = px.treemap(
            treemap_data,
            names=names,
            parents=parents,
            values=values,
            color_continuous_scale=color_continuous_scale,
            range_color=[0, max_severity],
            color=color,
            template="plotly_dark",
            hover_data=hoverdata,
        )
        treemap.update_traces(
            marker_cornerradius=4,
        )
        treemap.update_layout(height=DEFAULT_CHART_HEIGHT)
    treemap.update_traces(
        pathbar=dict(visible=False),
        hoverlabel=TREEMAP_HOVERLABEL,
    )
    if hovertemplate is not None:
        treemap.update_traces(
            hovertemplate=hovertemplate,
        )
    treemap.update_layout(
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
    treemap.update_traces(insidetextfont_size=20, selector=dict(type="treemap"))
    return treemap


def create_project_list(data):
    """Creates a list of the projects that have certain components """

    project = [project.split("-")[0] for project in data.columns]
    project_list = list(set(project))
    return project_list


def extract_component_name(turbine):
    """This function pulls the component name for the CorePhase and Phase components """

    parts = turbine.split('_')
    if len(parts) > 3:
        return '_'.join(parts[:3])
    return turbine


def map_mean_values(data, other_data):
    """" This function maps the transformer a,b,c mean values to the deviation component """

    # Initialize new columns in the original DataFrame
    data['A'] = 0
    data['B'] = 0
    data['C'] = 0

    for index, row in data.iterrows():
        component = row["ComponentReference"]
        # Find columns in other_data that are exactly the component reference
        mask = other_data.columns.str.contains(component)
        similar_components = other_data.loc[:, mask]
        similar_components = similar_components.mean()

        if not similar_components.empty:
            data.at[index, 'A'] = similar_components.iloc[0].round(0)
            data.at[index, 'B'] = similar_components.iloc[1].round(0)
            data.at[index, 'C'] = similar_components.iloc[2].round(0)

    return data


def generate_transformer_treemap(treemap_data_from_file, mean_dev_metric, start=None, end=None, component_type=None, project=None):
    """
     Generates a treemap plot using the Transformer data from Wind Farm object. - Jylen Tate

     Args:
         treemap_data_from_file (pd.DataFrame): This is the relevant dataset.
         mean_dev_metric (str): This values allows to know what metric to display
         start (Optional[datetime]): Start date of the time window to consider. Defaults to None.
         end (Optional[datetime]): End date of the time window to consider. Defaults to None.
         component_type (Optional[str]): String representing a specific component type to filter by.
     Defaults to None.

     Returns:
     plotly.graph_objs._figure.Figure: A treemap plot showing the severity of issues in each turbine/component.
     """
    if start is None:
        start = treemap_data_from_file.index[0]
    if end is None:
        end = treemap_data_from_file.index[-1]

    if mean_dev_metric == "Intra":
        # Determine the columns to use based on component_type
        dev_col_map = treemap_data_from_file.columns.str.contains(
            f"{component_type}" if component_type != "All" else "Dev"
        )

        # Filter the treemap data based on the selected columns and range
        treemap_data = treemap_data_from_file.loc[start:end, dev_col_map]
        project_list = create_project_list(treemap_data)

        # Further filter by project if specified
        if project != "All" and project in project_list:
            project_map = treemap_data.columns.str.contains(project)
            treemap_data = treemap_data.loc[start:end, project_map]

        # Filter columns for mean data and exclude specific patterns
        mean_col_map = treemap_data_from_file.columns.str.contains(
            "_mean") & ~treemap_data_from_file.columns.str.contains("|".join(["-DIR", "-YAW", "-LOST"]))
        mean_data = treemap_data_from_file.loc[start:end, mean_col_map]

        # Clean mean data column names
        mean_data.columns = [
            x.replace("_mean", "") if "_mean" in x else x for x in mean_data.columns
        ]

        # Gets data for transformer components - Jylen Tate
        mean_data.columns = mean_data.columns.map(
            lambda x: (
                turbine_component := f"{get_turbine(x)}-{KEY_TO_NAME.get(get_component_type(x), '')}",
                turbine_component if any(
                    component in turbine_component for component in [
                        ComponentTypes.TRANSFORMER_CORE_PHASE_A.value,
                        ComponentTypes.TRANSFORMER_CORE_PHASE_B.value,
                        ComponentTypes.TRANSFORMER_CORE_PHASE_C.value,
                        ComponentTypes.TRANSFORMER_PHASE_A.value,
                        ComponentTypes.TRANSFORMER_PHASE_B.value,
                        ComponentTypes.TRANSFORMER_PHASE_C.value
                    ]
                ) else None
            )[1]
        )
        mean_data = mean_data.loc[:, mean_data.columns.notna()]

        # Calculate severity and prepare data
        severity = treemap_data.mean().round(0)
        data = pd.DataFrame({"Turbine": treemap_data.columns, "Severity": severity.values})
        data["ComponentReference"] = data['Turbine'].apply(extract_component_name)
        max_severity = data["Severity"].max()
        data = map_mean_values(data, mean_data)
        data = data.sort_values(by="Severity", ascending=False).head(25)

        # Define hover template and data
        hovertemplate = (
            "<b>Turbine</b>: %{label}<br>"
            "<b>Avg Deviation</b>: %{customdata[0]}%<br>"
            "<b>A</b>: %{customdata[1]:.0f}°C<br>"
            "<b>B</b>: %{customdata[2]:.0f}°C<br>"
            "<b>C</b>: %{customdata[3]:.0f}°C<br>"
        )
        hoverdata = ["Severity", "A", "B", "C"]

        # Construct the treemap
        treemap = construct_styled_treemap(
            treemap_data=data,
            color_continuous_scale=COMP_TEMP_COLORSCALE,
            max_severity=max_severity,
            hovertemplate=hovertemplate,
            hoverdata=hoverdata,)

        return treemap

    elif mean_dev_metric == "Mean":

        mean_col_map = treemap_data_from_file.columns.str.contains(
            "_mean"
        ) & ~treemap_data_from_file.columns.str.contains(
            "|".join(["-DIR", "-YAW", "-LOST"])
        )
        # print('tm 398', start, end, treemap_data_from_file.loc[start:end, ~mean_col_map].copy())
        treemap_data = treemap_data_from_file.loc[start:end, ~mean_col_map].copy().sum()
        treemap_data = treemap_data.to_frame().reset_index()
        treemap_data.columns = ["Turbine", "Severity"]
        treemap_data["TurbineRaw"] = treemap_data["Turbine"]

        mean_data = treemap_data_from_file.loc[start:end, mean_col_map].copy().mean()
        mean_data.index = mean_data.index.str.replace("_mean", "")
        mean_data = mean_data.to_frame().reset_index()
        mean_data.columns = ["Turbine", "Mean"]

        project_component_pairs = mean_data["Turbine"].map(get_project_component)
        project_component_pairs = list(set(project_component_pairs))

        park_average_dict = {}
        for pc in project_component_pairs:
            matching_cols = [
                col for col in mean_data["Turbine"] if get_project_component(col) == pc
            ]
            park_average_dict[pc] = mean_data.loc[
                mean_data["Turbine"].isin(matching_cols), "Mean"
            ].mean()

        park_average_series = pd.Series(index=mean_data["Turbine"])

        for col in park_average_series.index:
            pc = get_project_component(col)
            park_average_series[col] = park_average_dict[pc]

        park_avg_data = park_average_series.to_frame().reset_index()
        park_avg_data.columns = ["Turbine", "Park Avg"]

        treemap_data = pd.merge(
            treemap_data, mean_data[["Turbine", "Mean"]], on="Turbine", how="left"
        )

        treemap_data = pd.merge(treemap_data, park_avg_data, on="Turbine", how="left")

        # Gets data for transformer components - Jylen Tate
        treemap_data["Turbine"] = treemap_data["Turbine"].apply(
            lambda x: f"{get_turbine(x)}-{KEY_TO_NAME.get(get_component_type(x), '')}" if any(
                component in f"{get_turbine(x)}-{KEY_TO_NAME.get(get_component_type(x), '')}" for component in
                [ComponentTypes.TRANSFORMER_CORE_PHASE_A.value, ComponentTypes.TRANSFORMER_CORE_PHASE_B.value,
                 ComponentTypes.TRANSFORMER_CORE_PHASE_C.value,
                 ComponentTypes.TRANSFORMER_PHASE_A.value, ComponentTypes.TRANSFORMER_PHASE_B.value,
                 ComponentTypes.TRANSFORMER_PHASE_C.value, ]) else None
        )
        treemap_data = treemap_data[treemap_data["Turbine"].notna()]

        if component_type != "All":
            treemap_data = treemap_data[
                treemap_data["Turbine"].str.contains(component_type)
            ]

        if project != "All":
            treemap_data = get_project_data(treemap_data, project)

        treemap_data = treemap_data.sort_values(by="Severity", ascending=False).head(25)

        # Scale the severity values to range [0, 1]
        max_severity = treemap_data["Severity"].max()

        treemap_data = treemap_data[treemap_data["Severity"] > 0].dropna()

        hovertemplate = (
            "<b>Turbine</b>: %{label}<br>"
            "<b>Mean Temperature</b>: %{customdata[0]:.0f}°C<br>"
            "<b>Park Avg Temperature</b>: %{customdata[1]:.0f}°C"
            "<extra></extra>"
        )
        hoverdata = ["Mean", "Park Avg"]
        treemap = construct_styled_treemap(
            treemap_data=treemap_data,
            color_continuous_scale=COMP_TEMP_COLORSCALE,
            max_severity=max_severity,
            hovertemplate=hovertemplate,
            hoverdata=hoverdata,
        )
        return treemap
