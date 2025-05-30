"""The Landing Page with navigation to the Wind & Solar."""

import dash
import dash_bootstrap_components as dbc

dash.register_page(
    __name__,
    path="/",
    title="iSight",
)


def layout():
    return dbc.Row(
        className="g-0",
        justify="around",
        children=[
            dbc.Col(
                children=dbc.NavLink(
                    children="Wind",
                    className="splash-page-card disabled-strong",
                    href=dash.get_relative_path("/wind"),
                ),
                sm=12,
                md=5,
            ),
            dbc.Col(
                children=dbc.NavLink(
                    children="Solar",
                    className="splash-page-card",
                    href=dash.get_relative_path("/weather-station"),
                ),
                sm=12,
                md=5,
            ),
        ],
    )
