"""A module that contains Heatmap Charts used in the App.

Heatmaps is a data visualization, essentially a 2D array of cells which
each are associated with data. In the application, heatmaps exclusively
appear inside and after clicking on a Treemap's cell. They are used to
display a more drilled-down version of the clicked cell.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from Charts.Hovertemplate import (
    append_units_and_round,
)
from Utils.Constants import (
    DEFAULT_PARSE_FUNCS,
)
from Utils.Transformers import (
    get_turbine,
)
from Utils.UiConstants import (
    DEFAULT_CHART_HEIGHT,
    COMPONENT_TEMPERATURE_SUBCHART_HEIGHT,
    REV_FAULT_METRIC_COLUMN_LOOKUP,
)


def make_styled_heatmap(z, x, y, hovertemplate=None, customdata=None, height=None):
    """A wrapper around Plotly's Heatmap that adds styling and coloring.

    Args:
        z: See plotly.graph_objects.Heatmap.z.
        x: See plotly.graph_objects.Heatmap.x.
        y: See plotly.graph_objects.Heatmap.y.
        hovertemplate: See plotly.graph_objects.Heatmap.hovertemplate.
        customdata: See plotly.graph_objects.Heatmap.hovertemplate.
        height: See plotly.graph_objects.Figure.layout.height.
    Returns:
        fig (plotly.graph_objects.Figure): The styled heatmap.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=z,
            x=x,
            y=y,
            colorscale="YlOrRd_r",
            hovertemplate=hovertemplate,
            customdata=customdata,
            colorbar=dict(
                orientation="h",
                thickness=10,
            ),
        )
    )

    fig.update_layout(
        height=height,
        template="plotly_dark",
        margin=dict(
            autoexpand=True,
            t=45,
            l=10,
            r=50,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=12), tickangle=270)
    fig.update_yaxes(side="right", gridcolor="rgba(0,0,0,0)")
    return fig


def make_styled_heatmap_multiindex(z, element_name, component_type, heatmap_toggle, customdata=None):
    """Create a heatmap using a dataframe that has a multiindex.

    This plotter function is used to generate the heatmap subcharts that
    spawn when a component of the Component Temperature Chart is clicked.

    Args:
        z (pd.DataFrame): A pandas DataFrame with MultiIndex columns.
        element_name (str): The turbine of the turbine-component that
            was originally clicked in the UI to spawn this heatmap.
        component_type (str): The component of the turbine-component that
            was originally clicked in the UI to spawn this heatmap.
        heatmap_toggle (str): Either "by-component" or "by-turbine". These
            are the possible values of the Dash radioitems UI component with
            the ID "heatmap-toggle"
        customdata (list of lists): ...
    Returns:
        fig (plotly.graph_objects.Figure): The styled heatmap with subplots for each metric.
    """
    if not isinstance(z, pd.DataFrame) or not isinstance(z.columns, pd.MultiIndex):
        raise ValueError("z must be a pandas DataFrame with MultiIndex columns")
    
    # Get unique metrics from the second level of the MultiIndex
    metrics = z.columns.get_level_values(1).unique()

    fig = go.Figure()
    for i, metric in enumerate(metrics[:1]):
        metric_data = z.xs(metric, level=1, axis=1)

        if heatmap_toggle == "by-component":
            line0 = f"<b>Turbine: {element_name}</b><br>"
            line = "Component: %{x}<br>"
        elif heatmap_toggle == "by-turbine":
            line0 = f"<b>Component: {component_type}</b><br>"
            line = "Turbine: %{x}<br>"
        hovertemplate = (
            line0 +
            line +
            "Date: %{y}<br>"
            "Severity: %{z:.2f}<br>"
            "<extra></extra>"
        )

        colorscale = [
            [0.0, "#6EB8FF"],
            [0.05, "#5CA6EC"],
            [0.1, "#4A94D9"],
            [0.15, "#3983C6"],
            [0.2, "#2871B3"],
            [0.25, "#1C60A0"],
            [0.3, "#154F8C"],
            [0.35, "#0F3E79"],
            [0.4, "#092D66"],
            [0.45, "#041C53"],
            [0.5, "#0E0404"],
            [0.55, "#3F0909"],
            [0.6, "#6F0E0E"],
            [0.65, "#9F1313"],
            [0.7, "#CF1818"],
            [0.75, "#E32D2D"],
            [0.8, "#F04242"],
            [0.85, "#F75757"],
            [0.9, "#FD6C6C"],
            [0.95, "#FF8181"],
            [1.0, "#FF9696"]
        ]
        fig.add_trace(
            go.Heatmap(
                z=metric_data.values,
                x=metric_data.columns,
                y=metric_data.index,
                colorscale=colorscale,
                zmid=0,
                hovertemplate=hovertemplate,
                customdata=customdata,
                colorbar=dict(
                    orientation="h",
                    thickness=10,
                    y=1 - (i * 0.2)
                ),
            ),
        )
 
    fig.update_layout(
        title="",
        height=COMPONENT_TEMPERATURE_SUBCHART_HEIGHT,
        template="plotly_dark",
        margin=dict(
            autoexpand=True,
            t=45,
            l=10,
            r=50,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=12))
    fig.update_yaxes(side="right", gridcolor="rgba(0,0,0,0)")
    return fig


def generate_comp_temp_heatmap(data_frame, lost_energy_df=None, mean_frame=None):
    """Make heatmap that appears upon drilling down on component treemap cell.

    Args:
        data_frame (pandas.DataFrame): The index is the date, the columns
            are turbine names, and values are their respective Severities.
        lost_energy_df (pandas.DataFrame): This comes from the
            output of the `filter_lost_energy` function. See its docstring
            for relevant info about its properties.
    Returns:
        (plotly.graph_objects.Figure): A Plotly heatmap.
    """

    fig = go.Figure()
    data_frame = data_frame.dropna(axis=1, how="all").drop_duplicates()
    data_frame = data_frame.sort_index(axis=1)

    # ensure both dataframes have same column order
    parse_turbine = get_turbine
    parse_comp = DEFAULT_PARSE_FUNCS["component_type_func"]

    # lost_energy is a proxy for by turbine
    if lost_energy_df is not None:
        x_arr = [parse_turbine(name) for name in data_frame]
        data_frame.sort_index(axis=1, inplace=True)

        row_mean = mean_frame.mean(axis=1)

        result_df = pd.DataFrame([row_mean.drop_duplicates()] * len(mean_frame.columns)).T

        result_df.reset_index(drop=True, inplace=True)
        result_df = result_df.fillna(0).sort_index(axis=1)
        park_avg = result_df.values

        for col in mean_frame.columns:
            col = col.replace("_mean", "")
            col = get_turbine(col) + "-Lost_Energy"
            if col not in lost_energy_df.columns:
                lost_energy_df[col] = [0] * len(mean_frame)

        lost_energy_df.sort_index(axis=1, inplace=True)

        component = parse_comp(data_frame.columns[0])

        # Create customdata
        customdata = [
            [mean, park, energy]
            for park, energy, mean in zip(
                park_avg, lost_energy_df.values, mean_frame.values
            )
        ]

        customdata_3D = np.array(customdata)

        customdata = np.transpose(customdata_3D, (0, 2, 1))

        hovertemplate = (
            "Turbine: %{x}<br>"
            f"Component: {component}<br>"
            "Date: %{y}<br>"
            "Mean Temperature: %{customdata[0]:.0f}°C<br>"
            "Park Average Temperature: %{customdata[1]:.0f}°C<br>"
            "Lost Energy: %{customdata[2]:.0d}MWh"
        )

    else:
        x_arr = [parse_comp(name) for name in data_frame]
        turbine = parse_turbine(data_frame.columns[0])
        transposed_df = mean_frame.T.dropna(how="all")
        mean_frame = transposed_df.T
        transposed_df["component_type"] = transposed_df.index.str.split("-").str[-1]
        park_avg_by_component = transposed_df.groupby("component_type").mean()

        # Broadcast the mean values to match the shape of the original dataframe
        result_df = mean_frame.copy()
        for col in mean_frame.columns:
            component = col.split("-")[-1]
            if component not in park_avg_by_component.index:
                result_df[col] = 0
            else:
                result_df[col] = park_avg_by_component.loc[component, :]

        result_df = result_df.sort_index(axis=True)

        # filter down to only the turbine that we need for performance
        result_df = result_df.loc[:, result_df.columns.str.contains(turbine)]
        mean_frame = mean_frame.loc[:, mean_frame.columns.str.contains(turbine)]
        data_frame = data_frame.loc[:, data_frame.columns.str.contains(turbine)]

        park_avg = result_df.values

        # Create customdata
        customdata = [[mean, park] for park, mean in zip(park_avg, mean_frame.values)]
        customdata_3D = np.array(customdata)
        customdata = np.transpose(customdata_3D, (0, 2, 1))

        hovertemplate = (
            f"Turbine: {turbine}<br>"
            "Component: %{x}<br>"
            "Date: %{y}<br>"
            "Mean Temperature: %{customdata[0]:.0f}°C<br>"
            "Park Average Temperature: %{customdata[1]:.0f}°C"
        )
    hovertemplate += "<extra></extra>"
    fig = make_styled_heatmap(
        z=data_frame.values,
        x=x_arr,
        y=data_frame.index,
        customdata=customdata,
        hovertemplate=hovertemplate,
        height=DEFAULT_CHART_HEIGHT + 100,
    )
    return fig


def generate_fault_heatmap(
    dataset,
    metric,
    fault_description,
):
    """Displays Turbines across time sharing the same fault code.

    Args:
        dataset (pandas.DataFrame): The dataset that contains the fault metrics.
            This dataset should come from the output of the `load_fault_daily_metrics`.
        metric (str): One of "Downtime", "Lost Energy", "Lost Revenue", or "Count".
        fault_description (str): The fault code description. eg. "REPAIR"
        start_date (datetime): The start date of the chart.
        end_date (datetime): The end date of the chart.

    Returns:
        fig (plotly.graph_objects.Figure): A Plotly heatmap.
    """
    fmt_metric = REV_FAULT_METRIC_COLUMN_LOOKUP[metric]
    dataset = dataset[dataset["Description"] == fault_description]
    dff = dataset[["Date", "Turbine", fmt_metric]]
    pivot_df = dff.pivot(index="Date", columns="Turbine", values=fmt_metric)

    z_hover = append_units_and_round(var="z", metric=metric)
    hovertemplate = f"Turbine: %{{x}}<br>Date: %{{y}}<br>{z_hover}<extra></extra>"
    fig = make_styled_heatmap(
        z=pivot_df.values,
        x=pivot_df.columns,
        y=pivot_df.index,
        hovertemplate=hovertemplate,
    )
    return fig


def generate_intra_heatmap(data_frame, project):
    """"Displays Turbines across time comparing the Transformer temperature deviations - Jylen Tate
    data_frame (pd.DataFrame): dataframe from load_treemap_dataset()
    project (string): value used to denote which Wind Site
    """

    dev_col_map = data_frame.columns.str.contains("Dev")
    data_frame = data_frame.loc[:, dev_col_map]

    parse_turbine = get_turbine
    data_frame = data_frame.filter(like=project)
    data_frame = data_frame[sorted(data_frame.columns)]
    data_frame = data_frame.round(0)
    x_arr = [parse_turbine(name) for name in data_frame]

    hovertemplate = (
        "Turbine: %{x}<br>"
        "Date: %{y}<br>"
        "Deviation: %{z}%<br>"
    )
    hovertemplate += "<extra></extra>"
    heatmap = make_styled_heatmap(z=data_frame.values, x=x_arr, y=data_frame.index, customdata=data_frame, hovertemplate=hovertemplate, height=600)

    return heatmap
