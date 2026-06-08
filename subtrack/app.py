from pathlib import Path

import dash
from dash import Dash, Input, Output, callback, clientside_callback, dcc, page_container, html
import dash_bootstrap_components as dbc
from flask import redirect, request

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
server.config["SESSION_COOKIE_SAMESITE"] = "Lax"
server.config["SESSION_COOKIE_HTTPONLY"] = True


@server.before_request
def require_auth():
    path = request.path
    # Allow Dash internals, static assets, login page, and the logout route.
    if (
        path.startswith("/_dash")
        or path.startswith("/_reload")
        or path.startswith("/assets")
        or path in ("/favicon.ico", "/login", "/do-logout")
    ):
        return None
    from flask import session
    if "user_id" not in session:
        return redirect("/login")
    return None


@server.route("/do-logout")
def do_logout():
    logout_user()
    return redirect("/login")


app.layout = dbc.Container(
    [
        # Single Location component — Dash requires exactly one per app.
        dcc.Location(id="app-url"),
        # guard_routes writes a URL path here when it needs to redirect; a
        # clientside_callback below reads it and calls window.location.href.
        dcc.Store(id="nav-signal", storage_type="memory", data=None),
        html.Div(id="_nav-target", style={"display": "none"}),
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
        ),
    ],
    fluid=True,
    className="app-root",
)

# When guard_routes sets nav-signal to a path, navigate immediately in the browser.
clientside_callback(
    "function(path) { if (path) { window.location.href = path; } return ''; }",
    Output("_nav-target", "children"),
    Input("nav-signal", "data"),
    prevent_initial_call=True,
)


@callback(
    Output("nav-signal", "data"),
    Output("sidebar-wrapper", "children"),
    Output("sidebar-wrapper", "style"),
    Output("navbar-wrapper", "children"),
    Output("navbar-wrapper", "style"),
    Input("app-url", "pathname"),
    prevent_initial_call=False,
)
def guard_routes(pathname: str | None):
    user = current_user()
    hidden = {"display": "none"}
    visible = {"display": "block"}

    if user is None:
        if pathname in (None, "/login"):
            return dash.no_update, "", hidden, "", hidden
        return "/login", "", hidden, "", hidden

    sidebar = build_sidebar(user.full_name, user.email, pathname or "/")
    navbar = build_navbar(user.full_name)

    if pathname == "/login":
        return "/", sidebar, visible, navbar, visible

    return dash.no_update, sidebar, visible, navbar, visible


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)