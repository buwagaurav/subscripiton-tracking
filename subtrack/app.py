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

# OAuth state is stored in the Flask session so it survives server restarts
# and works correctly with multi-process deployments.

def _store_state(state: str, code_verifier: str | None = None) -> None:
    from flask import session as fsess
    fsess["_oauth_state"] = state
    fsess["_oauth_cv"] = code_verifier
    fsess["_oauth_ts"] = time.time()
    fsess.modified = True


def _consume_state(state: str) -> tuple[bool, str | None]:
    from flask import session as fsess
    stored = fsess.pop("_oauth_state", None)
    cv     = fsess.pop("_oauth_cv", None)
    ts     = fsess.pop("_oauth_ts", 0.0)
    fsess.modified = True
    if stored is None or stored != state:
        return False, None
    if (time.time() - ts) > 300:  # 5-minute TTL
        return False, None
    return True, cv


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
    except Exception as exc:
        traceback.print_exc()
        import urllib.parse
        detail = urllib.parse.quote(str(exc)[:200], safe="")
        return redirect(f"/gmail-import?error=exchange_failed&detail={detail}")

    return redirect("/gmail-import")


@server.route("/auth/google/disconnect")
def google_auth_disconnect():
    from flask import session as fsess
    user_id = fsess.get("user_id")
    if user_id:
        clear_google_tokens(user_id)
    return redirect("/gmail-import")


app.index_string = """<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
    {%css%}
    <script>
        (function() {
            try {
                var raw = localStorage.getItem('theme-store');
                var theme = raw ? JSON.parse(raw) : 'light';
                if (theme === 'dark') {
                    document.documentElement.setAttribute('data-theme', 'dark');
                    document.documentElement.setAttribute('data-bs-theme', 'dark');
                    var s = document.getElementById('splash');
                    if (s) s.style.background = '#0f0f11';
                }
            } catch(e) {}
        })();
    </script>
</head>
<body>
    <div id="splash">
        <div class="splash-mark">ST</div>
        <div class="splash-brand">SubTrack</div>
        <div class="splash-dots">
            <span class="splash-dot"></span>
            <span class="splash-dot"></span>
            <span class="splash-dot"></span>
        </div>
    </div>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
    <script>
        (function() {
            var POLL_MS = 80, MAX_WAIT = 8000, elapsed = 0;
            var t = setInterval(function() {
                elapsed += POLL_MS;
                var root = document.querySelector('.app-root');
                if ((root && root.children.length) || elapsed >= MAX_WAIT) {
                    clearInterval(t);
                    var splash = document.getElementById('splash');
                    if (splash) {
                        splash.classList.add('splash-done');
                        setTimeout(function() {
                            if (splash.parentNode) splash.parentNode.removeChild(splash);
                        }, 450);
                    }
                }
            }, POLL_MS);
        })();
    </script>
</body>
</html>"""

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