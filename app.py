import dash
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="iSight Dashboard",
    use_pages=True,
    external_stylesheets=[dbc.themes.GRID, dbc.icons.BOOTSTRAP],
)

app.scripts.config.serve_locally = True
app.css.config.serve_locally = True
