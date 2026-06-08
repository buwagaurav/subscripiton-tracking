import dash
from dash import Input, Output, State, callback, dcc, html
import dash_bootstrap_components as dbc

from subtrack.auth import login_user


dash.register_page(__name__, path="/login", name="Login")


def layout() -> dbc.Container:
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
                                dbc.Button("Sign In", id="login-button", color="primary", className="w-100"),
                                dcc.Location(id="login-redirect", refresh=True),
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
