import dash
from dash import Input, Output, State, callback, dcc, html
import dash_bootstrap_components as dbc

from subtrack.auth import login_user
from subtrack import gmail


dash.register_page(__name__, path="/login", name="Login")


def layout(error: str = "") -> dbc.Container:
    error_messages = {
        "google_not_configured": "Google sign-in is not configured on this server.",
        "state_mismatch": "Sign-in session expired. Please try again.",
        "no_code": "Google did not return an authorization code.",
        "google_signin_failed": "Google sign-in failed. Please try again or use email/password.",
    }
    google_error = error_messages.get(error, "")
    google_configured = gmail.is_configured()

    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.Div("Onboarding", className="section-kicker"),
                                html.H1("Sign in to SubTrack", className="login-title"),
                                html.P(
                                    "Enter your email and password to access your subscriptions.",
                                    className="page-copy login-copy",
                                ),
                                dbc.Alert(id="login-alert", is_open=False, color="danger", className="mb-3"),
                                dbc.Label("Email", className="form-label"),
                                dbc.Input(
                                    id="login-email",
                                    type="email",
                                    placeholder="you@subtrack.dev",
                                    className="mb-3",
                                ),
                                dbc.Label("Password", className="form-label"),
                                dbc.Input(
                                    id="login-password",
                                    type="password",
                                    placeholder="Enter your password",
                                    className="mb-4",
                                ),
                                dbc.Button("Sign In", id="login-button", color="primary", className="w-100 mb-3"),
                                dcc.Location(id="login-redirect", refresh=True),
                                # ── Google Sign-In ──────────────────────────
                                html.Div(
                                    [
                                        html.Hr(className="my-3"),
                                        html.Div("or", className="text-center text-muted small mb-3"),
                                        html.A(
                                            [
                                                html.Img(
                                                    src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg",
                                                    height="20",
                                                    className="me-2",
                                                ),
                                                "Sign in with Google",
                                            ],
                                            href="/auth/google/signin",
                                            className="btn btn-outline-light w-100 d-flex align-items-center justify-content-center",
                                        ),
                                        dbc.Alert(
                                            google_error,
                                            color="warning",
                                            is_open=bool(google_error),
                                            className="mt-3 mb-0",
                                        ),
                                    ]
                                ) if google_configured else html.Div(),
                            ]
                        ),
                        className="panel-card login-card",
                    ),
                    lg=5,
                    md=7,
                    xs=11,
                ),
                className="justify-content-center login-shell",
            )
        ],
        fluid=True,
        className="page-shell login-page-shell",
    )


@callback(
    Output("login-redirect", "pathname"),
    Output("login-alert", "children"),
    Output("login-alert", "is_open"),
    Input("login-button", "n_clicks"),
    State("login-email", "value"),
    State("login-password", "value"),
    prevent_initial_call=True,
)
def handle_login(_: int, email: str | None, password: str | None):
    if not email or not password:
        return dash.no_update, "Enter both email and password.", True
    user = login_user(email, password)
    if user is None:
        return dash.no_update, "Invalid credentials. Please try again.", True
    return "/", "", False
