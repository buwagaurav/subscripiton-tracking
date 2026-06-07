import dash
from dash import Input, Output, State, callback, dcc, html
import dash_bootstrap_components as dbc

from subtrack.auth import current_user, login_user
from subtrack.database.db import fetch_demo_users


dash.register_page(__name__, path="/login", name="Login")


def layout() -> dbc.Container:
    demo_users = fetch_demo_users()
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div("Onboarding", className="section-kicker"),
                                    html.H1("Sign in to SubTrack", className="login-title"),
                                    html.P(
                                        "Use one of the seeded demo accounts below to explore authenticated subscription tracking.",
                                        className="page-copy login-copy",
                                    ),
                                    dbc.Alert(id="login-alert", is_open=False, color="danger", className="mb-3"),
                                    dbc.Label("Email", className="form-label"),
                                    dbc.Input(
                                        id="login-email",
                                        type="email",
                                        placeholder="aarav@subtrack.dev",
                                        className="mb-3",
                                    ),
                                    dbc.Label("Password", className="form-label"),
                                    dbc.Input(
                                        id="login-password",
                                        type="password",
                                        placeholder="Enter demo password",
                                        className="mb-4",
                                    ),
                                    dbc.Button("Sign In", id="login-button", color="primary", className="w-100"),
                                    dcc.Location(id="login-redirect"),
                                ]
                            ),
                            className="panel-card login-card",
                        ),
                        lg=5,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div("Demo Accounts", className="section-kicker"),
                                    html.H3("Seeded users", className="section-title"),
                                    html.Div(
                                        [
                                            dbc.Card(
                                                dbc.CardBody(
                                                    [
                                                        html.Div(user["full_name"], className="demo-user-name"),
                                                        html.Div(user["email"], className="demo-user-email"),
                                                        html.Div(
                                                            f"Password: {user['password']}",
                                                            className="demo-user-password",
                                                        ),
                                                    ]
                                                ),
                                                className="demo-user-card",
                                            )
                                            for user in demo_users
                                        ]
                                    ),
                                ]
                            ),
                            className="panel-card login-demo-card",
                        ),
                        lg=7,
                    ),
                ],
                className="g-4 justify-content-center login-shell",
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
    if current_user() is not None:
        return "/", "", False
    if not email or not password:
        return dash.no_update, "Enter both email and password.", True
    user = login_user(email, password)
    if user is None:
        return dash.no_update, "Invalid credentials. Use one of the seeded demo accounts.", True
    return "/", "", False
