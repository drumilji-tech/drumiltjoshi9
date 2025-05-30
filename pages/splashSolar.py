"""The App's Landing Page with navigation to its contained Pages."""

import dash
import dash_bootstrap_components as dbc

dash.register_page(
    __name__,
    path="/solar",
    title="iSight (Solar)",
)


def layout():
    return dbc.Row(
        className="g-0",
        justify="around",
        children=[
            dbc.Col(
                children=dbc.NavLink(
                    children="Weather Station",
                    className="splash-page-card",
                    href=dash.get_relative_path("/weather-station"),
                ),
                sm=12,
                md=5,
            ),
            dbc.Col(
                children=dbc.NavLink(
                    children="Inverter Performance",
                    className="splash-page-card",
                    href=dash.get_relative_path("/inverter-performance"),
                ),
                sm=12,
                md=5,
            ),
        ],
    )
