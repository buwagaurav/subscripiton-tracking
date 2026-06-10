import os
from pathlib import Path
import logging
import time
import traceback

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import dash
from dash import Dash, Input, Output, State, callback, clientside_callback, dcc, page_container, html
import dash_bootstrap_components as dbc
from flask import redirect, request

from subtrack.auth import current_user, logout_user
from subtrack.components.navbar import build_navbar
from subtrack.components.sidebar import build_sidebar
from subtrack.database.db import (
    clear_google_tokens,
    find_or_create_google_user,
    generate_notifications,
    get_unread_count,
    init_db,
    save_google_tokens,
)
from subtrack import gmail

APP_DIR = Path(__file__).resolve().parent

init_db()

app = Dash(
    __name__,
    use_pages=True,
    pages_folder=str(APP_DIR / "pages"),
    assets_folder=str(APP_DIR / "assets"),
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="SubTrack",
)
server = app.server
server.secret_key = os.environ.get("SECRET_KEY", "subtrack-mvp-secret-key")
server.config["SESSION_COOKIE_SAMESITE"] = "Lax"
server.config["SESSION_COOKIE_HTTPONLY"] = True
server.config["SESSION_COOKIE_SECURE"] = False

# Server-side store for OAuth CSRF states — avoids session-cookie round-trip issues.
# Maps state → (timestamp, code_verifier). Works for single-process (dev) deployments.
_OAUTH_STATES: dict[str, tuple[float, str | None]] = {}
_STATE_TTL = 300  # 5 minutes


def _store_state(state: str, code_verifier: str | None = None) -> None:
    now = time.time()
    _OAUTH_STATES[state] = (now, code_verifier)
    expired = [s for s, (t, _) in list(_OAUTH_STATES.items()) if now - t > _STATE_TTL]
    for s in expired:
        _OAUTH_STATES.pop(s, None)


def _consume_state(state: str) -> tuple[bool, str | None]:
    entry = _OAUTH_STATES.pop(state, None)
    if entry is None:
        return False, None
    ts, code_verifier = entry
    if (time.time() - ts) > _STATE_TTL:
        return False, None
    return True, code_verifier


@server.before_request
def require_auth():
    path = request.path
    # Allow Dash internals, static assets, login page, and the logout route.
    if (
            path.startswith("/_dash")
            or path.startswith("/_reload")
            or path.startswith("/assets")
            or path in (
            "/favicon.ico",
            "/login",
            "/do-logout",
            "/auth/google/signin",
            "/auth/google/signin/callback",
    )
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


@server.route("/auth/google/signin")
def google_signin_start():
    if not gmail.is_configured():
        return redirect("/login?error=google_not_configured")
    auth_url, state, code_verifier = gmail.get_signin_url()
    _store_state(state, code_verifier)
    return redirect(auth_url)


@server.route("/auth/google/signin/callback")
def google_signin_callback():
    from flask import session as fsess

    state = request.args.get("state", "")
    valid, code_verifier = _consume_state(state)
    if not valid:
        return redirect("/login?error=state_mismatch")

    code = request.args.get("code")
    if not code:
        return redirect("/login?error=no_code")

    try:
        info = gmail.exchange_signin_code(code, code_verifier)
        user = find_or_create_google_user(
            info["google_sub"], info["email"], info["name"]
        )
        fsess["user_id"] = user.id
        fsess.modified = True
    except Exception:
        traceback.print_exc()
        return redirect("/login?error=google_signin_failed")

    return redirect("/")


@server.route("/auth/google")
def google_auth_start():
    from flask import session as fsess
    if "user_id" not in fsess:
        return redirect("/login")
    if not gmail.is_configured():
        return redirect("/gmail-import")
    auth_url, state, code_verifier = gmail.get_auth_url()
    _store_state(state, code_verifier)
    return redirect(auth_url)


@server.route("/auth/google/callback")
def google_auth_callback():
    from flask import session as fsess
    if "user_id" not in fsess:
        return redirect("/login")

    state = request.args.get("state", "")
    valid, code_verifier = _consume_state(state)
    if not valid:
        return redirect("/gmail-import?error=state_mismatch")

    code = request.args.get("code")
    if not code:
        return redirect("/gmail-import?error=no_code")

    try:
        tokens = gmail.exchange_code(code, code_verifier)
        save_google_tokens(
            fsess["user_id"],
            tokens["access_token"],
            tokens.get("refresh_token"),
            tokens.get("expiry"),
        )
    except Exception:
        return redirect("/gmail-import?error=exchange_failed")

    return redirect("/gmail-import")


@server.route("/auth/google/disconnect")
def google_auth_disconnect():
    from flask import session as fsess
    user_id = fsess.get("user_id")
    if user_id:
        clear_google_tokens(user_id)
    return redirect("/gmail-import")


app.layout = dbc.Container(
    [
        # Single Location component — Dash requires exactly one per app.
        dcc.Location(id="app-url"),
        # Polls for new notifications every 60 seconds.
        dcc.Interval(id="notif-interval", interval=60_000, n_intervals=0),
        # guard_routes writes a URL path here when it needs to redirect; a
        # clientside_callback below reads it and calls window.location.href.
        dcc.Store(id="nav-signal", storage_type="memory", data=None),
        html.Div(id="_nav-target", style={"display": "none"}),
        # Persists light/dark preference across sessions.
        dcc.Store(id="theme-store", storage_type="local", data="light"),
        html.Div(id="theme-applier", style={"display": "none"}),
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

# Apply theme to <html> element whenever the store value changes (including on load).
clientside_callback(
    """
    function(theme) {
        var t = theme || 'light';
        document.documentElement.setAttribute('data-theme', t);
        document.documentElement.setAttribute('data-bs-theme', t);
        return '';
    }
    """,
    Output("theme-applier", "children"),
    Input("theme-store", "data"),
    prevent_initial_call=False,
)

# Toggle dark/light when the navbar button is clicked.
clientside_callback(
    """
    function(n_clicks, current_theme) {
        if (!n_clicks) return window.dash_clientside.no_update;
        return current_theme === 'dark' ? 'light' : 'dark';
    }
    """,
    Output("theme-store", "data"),
    Input("theme-toggle-btn", "n_clicks"),
    State("theme-store", "data"),
    prevent_initial_call=True,
)

# Same toggle for the login page (navbar is hidden there).
clientside_callback(
    """
    function(n_clicks, current_theme) {
        if (!n_clicks) return window.dash_clientside.no_update;
        return current_theme === 'dark' ? 'light' : 'dark';
    }
    """,
    Output("theme-store", "data", allow_duplicate=True),
    Input("login-theme-toggle", "n_clicks"),
    State("theme-store", "data"),
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


@callback(
    Output("notif-badge", "children"),
    Output("notif-badge", "style"),
    Input("notif-interval", "n_intervals"),
    Input("app-url", "pathname"),
    prevent_initial_call=False,
)
def refresh_notif_badge(_, pathname):
    user = current_user()
    if user is None:
        return "", {"display": "none"}
    generate_notifications(user.id)
    count = get_unread_count(user.id)
    if count == 0:
        return "", {"display": "none"}
    return str(count), {"display": "flex"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)