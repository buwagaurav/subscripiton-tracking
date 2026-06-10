import dash
from dash import Input, Output, State, callback, dcc, html
import dash_bootstrap_components as dbc

from subtrack.auth import login_user
from subtrack.database.db import create_user
from subtrack import gmail


dash.register_page(__name__, path="/login", name="Login")

_DEMO_USERS = [
    ("Aarav S.", "aarav@subtrack.dev", "Aarav@123"),
    ("Diya R.",  "diya@subtrack.dev",  "Diya@123"),
    ("Rohan M.", "rohan@subtrack.dev", "Rohan@123"),
    ("Sara K.",  "sara@subtrack.dev",  "Sara@123"),
]


def layout(error: str = "") -> dbc.Container:
    error_messages = {
        "google_not_configured": "Google sign-in is not configured on this server.",
        "state_mismatch":        "Sign-in session expired. Please try again.",
        "no_code":               "Google did not return an authorization code.",
        "google_signin_failed":  "Google sign-in failed. Try email/password instead.",
    }
    google_error   = error_messages.get(error, "")
    google_enabled = gmail.is_configured()

    demo_cards = [
        html.Div(
            [
                html.Div([
                    html.Div(name, className="demo-user-name"),
                    html.Div(email, className="demo-user-email"),
                ]),
                html.Div(password, className="demo-user-password"),
            ],
            className="demo-user-card",
        )
        for name, email, password in _DEMO_USERS
    ]

    signin_tab = dbc.Tab(
        [
            dbc.Alert(id="login-alert", is_open=False, color="danger",
                      className="mb-3", style={"borderRadius": "var(--r-sm)"}),
            dbc.Label("Email address", className="form-label"),
            dbc.Input(id="login-email", type="email",
                      placeholder="you@example.com", className="mb-3"),
            dbc.Label("Password", className="form-label"),
            dbc.Input(id="login-password", type="password",
                      placeholder="Enter your password", className="mb-4"),
            dbc.Button("Sign in", id="login-button", color="primary",
                       className="w-100 mb-1"),

            html.Div([
                html.Div("or", className="login-divider"),
                html.A(
                    [
                        html.Img(
                            src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg",
                            height="18",
                        ),
                        html.Span("Sign in with Google"),
                    ],
                    href="/auth/google/signin",
                    className="google-btn",
                ),
                dbc.Alert(google_error, color="warning", is_open=bool(google_error),
                          className="mt-3 mb-0",
                          style={"borderRadius": "var(--r-sm)"}),
            ]) if google_enabled else html.Div(),

            html.Div("Demo accounts", className="demo-section-label"),
            html.Div(demo_cards),
        ],
        label="Sign in",
        tab_id="signin",
    )

    signup_tab = dbc.Tab(
        [
            dbc.Alert(id="signup-alert", is_open=False, color="danger",
                      className="mb-3", style={"borderRadius": "var(--r-sm)"}),
            dbc.Label("Full name", className="form-label"),
            dbc.Input(id="signup-name", type="text",
                      placeholder="Your name", className="mb-3"),
            dbc.Label("Email address", className="form-label"),
            dbc.Input(id="signup-email", type="email",
                      placeholder="you@example.com", className="mb-3"),
            dbc.Label("Password", className="form-label"),
            dbc.Input(id="signup-password", type="password",
                      placeholder="Create a password", className="mb-3"),
            dbc.Label("Confirm password", className="form-label"),
            dbc.Input(id="signup-confirm", type="password",
                      placeholder="Repeat your password", className="mb-4"),
            dbc.Button("Create account", id="signup-button", color="primary",
                       className="w-100"),
        ],
        label="Create account",
        tab_id="signup",
    )

    return dbc.Container(
        [
            # Floating theme toggle — visible on login page since navbar is hidden
            html.Button(
                [html.I(className="bi bi-moon"), html.I(className="bi bi-sun")],
                id="login-theme-toggle",
                className="notif-btn theme-toggle-btn",
                n_clicks=0,
                title="Toggle dark mode",
                style={
                    "position": "fixed",
                    "top": "1rem",
                    "right": "1.25rem",
                    "zIndex": 1000,
                    "cursor": "pointer",
                },
            ),
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.Div("ST", className="login-logo-mark"),
                            html.H1("SubTrack", className="login-title"),
                            html.P(
                                "Track every subscription in one clean view.",
                                className="login-subtitle",
                            ),
                            dcc.Location(id="login-redirect", refresh=True),
                            dbc.Tabs(
                                [signin_tab, signup_tab],
                                active_tab="signin",
                                className="login-tabs",
                            ),
                        ],
                        className="login-card",
                    ),
                    lg=5, md=7, xs=11,
                ),
                className="justify-content-center align-items-center",
                style={"minHeight": "100vh"},
            ),
        ],
        fluid=True,
        className="page-shell",
        style={"background": "var(--bg)"},
    )


@callback(
    Output("login-redirect", "pathname"),
    Output("login-alert",    "children"),
    Output("login-alert",    "is_open"),
    Input("login-button",    "n_clicks"),
    State("login-email",     "value"),
    State("login-password",  "value"),
    prevent_initial_call=True,
)
def handle_login(_: int, email: str | None, password: str | None):
    if not email or not password:
        return dash.no_update, "Enter both email and password.", True
    user = login_user(email, password)
    if user is None:
        return dash.no_update, "Invalid email or password.", True
    return "/", "", False


@callback(
    Output("login-redirect",  "pathname", allow_duplicate=True),
    Output("signup-alert",    "children"),
    Output("signup-alert",    "is_open"),
    Input("signup-button",    "n_clicks"),
    State("signup-name",      "value"),
    State("signup-email",     "value"),
    State("signup-password",  "value"),
    State("signup-confirm",   "value"),
    prevent_initial_call=True,
)
def handle_signup(_: int, name: str | None, email: str | None,
                  password: str | None, confirm: str | None):
    if not name or not email or not password or not confirm:
        return dash.no_update, "All fields are required.", True
    if password != confirm:
        return dash.no_update, "Passwords do not match.", True
    if len(password) < 6:
        return dash.no_update, "Password must be at least 6 characters.", True

    user = create_user(name, email, password)
    if user is None:
        return dash.no_update, "An account with that email already exists.", True

    login_user(email, password)
    return "/", "", False
