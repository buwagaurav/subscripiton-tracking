from dash import html
import dash_bootstrap_components as dbc


def build_navbar(user_name: str | None = None) -> dbc.Navbar:
    return dbc.Navbar(
        dbc.Container(
            [
                html.Div(
                    [
                        html.Div("SubTrack", className="brand-title"),
                        html.Div(
                            "Subscription intelligence for everyday spending",
                            className="brand-subtitle",
                        ),
                    ]
                ),
                html.Div(
                    [
                        dbc.Badge("MVP", color="light", text_color="dark", className="app-badge"),
                        html.Div(user_name or "", className="nav-user-name"),
                        dbc.Button("Logout", id="logout-button", color="dark", className="logout-button"),
                    ],
                    className="nav-actions",
                ),
            ],
            fluid=True,
        ),
        color="transparent",
        dark=True,
        className="top-navbar",
    )
