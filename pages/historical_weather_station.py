"""Historical Weather Station Page."""

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import (
    callback,
    ctx,
    dash_table,
    dcc,
    html,
    Input,
    Output,
    State,
)
from dash.dash_table.Format import Format, Group

from Model.DataAccess import Databricks_Repository
from Utils.ISightConstants import (
    HISTORICAL_WS_COLUMNS_WITH_COMMA_FORMAT,
    MONTH_FULL_NAME_LOOKUP,
    QUARTER_FULL_NAME_LOOKUP,
)

COMPARISON_TABLE_TITLE = "Meteorological & Historical Comparison"
DEFAULT_YEAR = 2024

dash.register_page(
    __name__,
    path="/historical-weather-station",
    title="Historical Weather Station",
)


def layout():
    year_label_control = html.Div(
        children=[
            html.Label(
                htmlFor="year-comparison-table",
                children="Year",
            ),
            dcc.Dropdown(
                id="year-comparison-table",
                value=DEFAULT_YEAR,
                clearable=False,
            ),
        ],
    )
    period_label_control = html.Div(
        children=[
            html.Label(
                htmlFor="period-comparison-table",
                children="Period",
            ),
            dcc.Dropdown(
                id="period-comparison-table",
                options=["Month", "Quarter"],
                value=None,
                clearable=True,
            ),
        ],
    )
    selection_label_control = html.Div(
        children=[
            html.Label(
                htmlFor="selection-comparison-table",
                children="Selection",
            ),
            dcc.Dropdown(
                id="selection-comparison-table",
                clearable=True,
            ),
        ],
    )

    update_table_control = html.Div(
        children=[
            html.Label(
                htmlFor="update-comparison-table",
                children=".",
                style={"visibility": "hidden"},
            ),
            html.Button(
                id="update-comparison-table",
                className="download-btn comparion-table-download-btn",
                children="Update Table",
            ),
        ],
    )

    download_label_control = html.Div(
        children=[
            html.Label(
                htmlFor="download-comparison-data",
                children=".",
                style={"visibility": "hidden"},
            ),
            html.Button(
                id="download-comparison-data",
                className="inverted-download-btn comparion-table-download-btn",
                children=html.Span([
                    html.I(id="info-icon", className="bi bi-download me-2"),
                    html.Span("Download"),
                ]),
            ),
        ]
    )

    comparison_table_controls = dbc.Row(
        className="gy-0",
        align="center",
        justify="evenly",
        style={"marginBottom": "1rem"},
        children=[
            dbc.Col(
                children=year_label_control,
                md=5,
            ),
            dbc.Col(
                children=period_label_control,
                md=2,
            ),
            dbc.Col(
                children=selection_label_control,
                md=2,
            ),
            dbc.Col(
                children=update_table_control,
                md=2,
            ),
            dbc.Col(
                children=download_label_control,
                md=1,
            ),
        ],
    )

    poe_latex_equation = dcc.Markdown('''                                 
    A statistical metric describing the probability that the particular value will be met or exceeded, based on historical records.

    | **Value**    | **Interpretation**     | **Explanation**     |
    | :------------- | :----------  | :----------- |
    | P50   | Average insolation value. | N.A. |
    | P90   | Lower than average insolation value. | 10% of historical records are below the value and 90% are above. |
    | P10   | Higher than average insolation value. | 90% of historical records are below the value and 10% are above. |                                      

    Probability of Exceedance is defined as $P(X > x) = \\frac{N-r+1}{N+1}$
                       
    where:
    - $P(X > x)$ is the probability that the variable X exceeds the value x.
    - $N$ is the total number of observations in the dataset.
    - $r$ is the rank of the value $$x$$ when the dataset is sorted in ascending order
      - (with 1 being the smallest value).

    ''', mathjax=True)

    poe_details_popover = html.Div(
        id="poe-details-popover",
        className="poe-details-popover",
        children=[
            dbc.Button(
                className="poe-details-button",
                children=[
                    html.Span([
                        html.I(id="info-icon", className="bi bi-info-circle-fill me-2"),
                        html.Span("Info about Probability of Exceedance"),
                    ])
                ],
                id="component-target",
                n_clicks=0,
            ),
            dbc.Popover(
                children=[poe_latex_equation],
                body=True,
                target="component-target",
                trigger="click",
                flip=False,
                placement="left-start",
            ),
        ],
    )

    HEADER_STYLE = {"fontWeight": 400, "color": "#FFF", "margin": 0}
    return dbc.Container(
        fluid=True,
        class_name="wrap",
        children=[
            dcc.Download(id="download-comparison-table-container"),
            html.Div(
                className="card",
                children=[
                    html.H2(
                        id="comparison-table-title",
                        children=COMPARISON_TABLE_TITLE,
                        style=HEADER_STYLE,
                    ),
                    comparison_table_controls,
                    poe_details_popover,
                    dash_table.DataTable(
                        id="comparison-table",
                        css=[
                            {
                                "selector": ".dash-table-tooltip",
                                "rule": "background-color: rgb(50, 50, 50); color: var(--text);",
                            }
                        ],
                        fixed_rows={"headers": True},
                        tooltip_duration=1000*30,
                        style_header={
                            "backgroundColor": "rgb(30, 30, 30)",
                            "color": "var(--text)",
                            "textAlign": "center",
                            "textDecoration": "underline",
                            "textDecorationStyle": "dotted",
                        },
                        style_data={
                            "backgroundColor": "rgb(50, 50, 50)",
                            "color": "var(--text)",
                            "textAlign": "center",
                        },
                        style_cell={
                            'minWidth': 95, 'maxWidth': 95, 'width': 95,
                        },
                    ),
                    html.P(
                        id="last-updated-callout-hws",
                        className="last-updated-callout",
                    ),
                ],
            ),
        ]
    )


@callback(
    Output("last-updated-callout-hws", "children"),
    Input("url", "pathname"),
)
def update_hws_last_updated_callout(url):
    conn = Databricks_Repository()
    table_name = f"{conn.solar_catalog}.isight.historical_weather_station"
    last_updated = conn.get_table_last_updated(table_name=table_name)
    return f"Data for the Historical Weather Station was Last Updated on {last_updated}."

@callback(
    Output("comparison-table", "data"),
    Output("comparison-table", "columns"),
    Output("comparison-table", "tooltip_header"),
    Output("comparison-table-title", "children"),
    Input("update-comparison-table", "n_clicks"),
    State("year-comparison-table", "value"),
    State("period-comparison-table", "value"),
    State("selection-comparison-table", "value"),
)
def populate_comparison_table(
    n_clicks,
    year,
    period,
    selection,
):
    conn = Databricks_Repository()
    df = conn.get_historical_weather_station_table(
        year=year,
        period=period,
        selection=selection,
    )

    data = df.to_dict("records")

    columns = []
    for col in df.columns:
        column_spec = {"id": col, "name": col}
        if col in HISTORICAL_WS_COLUMNS_WITH_COMMA_FORMAT:
            column_spec["type"] = "numeric"
            column_spec["format"] = Format().group(True)
        columns.append(column_spec)

    current_period = "NA"
    if selection is None:
        current_period = year
    elif period == "Month":
        current_period = MONTH_FULL_NAME_LOOKUP[selection]
    elif period == "Quarter":
        current_period = QUARTER_FULL_NAME_LOOKUP[selection]

    HWS_TOOLTIP_LOOKUP = {
        "GHI SA (kWh/m²)": f"Insolation from {current_period}, from SolarAnywhere",
        "SA Typical GHI Year (kWh/m²)": f"### Typical insolation for {current_period}, from SolarAnywhere\n\nRoughly represents the typical {current_period} across all historical years [1998 - Present]",
        "PAMA Budget GHI (kWh/m²)": f"Budgeted GHI for {current_period}, provided by PAMA",
        "Variance to PAMA (%)": f"The percent difference of the 'GHI SA', compared to 'PAMA Budget GHI'\n\n(GHI SA - PAMA) / (PAMA)",
    }

    tooltip_header = {
        c: {'value': HWS_TOOLTIP_LOOKUP[c], 'type': 'markdown'}
        for c in HWS_TOOLTIP_LOOKUP.keys()
    }

    # update title based on the user inputs
    base_title = COMPARISON_TABLE_TITLE
    title = base_title
    if period is None or selection is None and year != None:
        title += f" for {year}"
    elif period == "Month" and selection is not None:
        title += f" for {MONTH_FULL_NAME_LOOKUP[selection]}, {year}"
    elif period == "Quarter" and selection is not None:
        title += f" for Q{selection}, {year}"

    return data, columns, tooltip_header, title


@callback(
    Output("selection-comparison-table", "value"),
    Output("selection-comparison-table", "options"),
    Input("period-comparison-table", "value"),
    prevent_initial_callback=True,
)
def update_selection_options(period):
    if period == "Month":
        options = [
            {"value": val, "label": MONTH_FULL_NAME_LOOKUP[val]}
            for val in MONTH_FULL_NAME_LOOKUP.keys()
        ]
    elif period == "Quarter":
        options = [
            {"value": val, "label": QUARTER_FULL_NAME_LOOKUP[val]}
            for val in [1, 2, 3, 4]
        ]
    else:
        options = []
    return None, options

@callback(
    Output("update-comparison-table", "style"),
    Input("period-comparison-table", "value"),
    Input("selection-comparison-table", "value"),
)
def disable_button_to_update_table(period, selection):
    disabled_style = {
        "cursor": "default",
        "pointer-events": "none",
        "opacity": 0.3,
    }
    enabled_style = {
        "cursor": "pointer",
        "opacity": 1,
    }
    if (
        (period == None and selection == None) or
        (period != None and selection != None)
    ):
        return enabled_style
    return disabled_style

@callback(
    Output("year-comparison-table", "value"),
    Output("year-comparison-table", "options"),
    Input("url", "pathname"),
)
def populate_year_options(pathname):
    conn = Databricks_Repository()
    min_year, max_year = conn.get_historical_weather_station_year_range()
    options = [
        {"value": year, "label": year} for year in list(range(max_year, min_year - 1, -1))
    ]
    init_value = options[0]["value"]
    return init_value, options

@callback(
    Output("download-comparison-table-container", "data"),
    Input("download-comparison-data", "n_clicks"),
    State("comparison-table", "data"),
    State("comparison-table-title", "children"),
    prevent_initial_callback=True,
)
def download_comparison_data(n, table_data, title):
    if n is None:
        return dash.no_update
    df = pd.DataFrame(table_data)

    title = title.replace("&", "and")
    title = title.replace(" ", "_")
    return dcc.send_data_frame(df.to_csv, f"{title}.csv")
