from pathlib import Path

import dash
from dash import Dash, Input, Output, callback, dcc, page_container, html
import dash_bootstrap_components as dbc

from subtrack.auth import current_user, logout_user
from subtrack.components.navbar import build_navbar
from subtrack.components.sidebar import build_sidebar
from subtrack.database.db import init_db


APP_DIR = Path(__file__).resolve().parent

init_db()

app = Dash(
    __name__,
    use_pages=True,
    pages_folder=str(APP_DIR / "pages"),
    assets_folder=str(APP_DIR / "assets"),
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="SubTrack",
)
server = app.server
server.secret_key = "subtrack-mvp-secret-key"


app.layout = dbc.Container(
    [
        dcc.Location(id="app-url"),
        html.Div(id="route-redirect"),
        dbc.Row(
            [
                dbc.Col(id="sidebar-wrapper", xs=12, lg=3, xl=2, className="sidebar-column"),
                dbc.Col(
                    [
                        html.Div(id="navbar-wrapper"),
                        html.Main(page_container, className="content-shell"),
                    ],
                    xs=12,
                    lg=9,
                    xl=10,
                    className="content-column",
                ),
            ],
            className="app-frame g-0",
        )
    ],
    fluid=True,
    className="app-root",
)


@callback(
    Output("route-redirect", "children"),
    Output("sidebar-wrapper", "children"),
    Output("sidebar-wrapper", "style"),
    Output("navbar-wrapper", "children"),
    Output("navbar-wrapper", "style"),
    Input("app-url", "pathname"),
    Input("logout-button", "n_clicks"),
    prevent_initial_call=False,
)
def guard_routes(pathname: str | None, _: int | None):
    triggered = dash.ctx.triggered_id
    if triggered == "logout-button":
        logout_user()
        return (
            dcc.Location(pathname="/login", id="logout-redirect"),
            "",
            {"display": "none"},
            "",
            {"display": "none"},
        )

    user = current_user()
    hidden = {"display": "none"}
    visible = {"display": "block"}

    if user is None:
        if pathname == "/login":
            return "", "", hidden, "", hidden
        return dcc.Location(pathname="/login", id="auth-redirect"), "", hidden, "", hidden

    sidebar = build_sidebar(user.full_name, user.email)
    navbar = build_navbar(user.full_name)

    if pathname == "/login":
        return dcc.Location(pathname="/", id="home-redirect"), sidebar, visible, navbar, visible
    return "", sidebar, visible, navbar, visible


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
