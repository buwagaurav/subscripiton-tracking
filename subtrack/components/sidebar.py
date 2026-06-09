from dash import dcc, html
import dash_bootstrap_components as dbc


def build_sidebar(
    user_name: str | None = None,
    user_email: str | None = None,
    pathname: str = "/",
) -> html.Div:
    nav_links = [
        ("Overview", "/"),
        ("Subscriptions", "/subscriptions"),
        ("Analytics", "/analytics"),
        ("Gmail Import", "/gmail-import"),
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.Div("ST", className="sidebar-logo"),
                    html.Div(
                        [
                            html.Div("SubTrack", className="sidebar-title"),
                            html.Div("Single view of recurring spend", className="sidebar-copy"),
                        ]
                    ),
                ],
                className="sidebar-header",
            ),
            html.Div(
                [
                    html.Div(user_name or "Guest", className="sidebar-user-name"),
                    html.Div(user_email or "Login required", className="sidebar-user-email"),
                ],
                className="sidebar-user-card",
            ),
            # dcc.Link goes through Dash's React Router so _pages_content fires correctly.
            html.Nav(
                [
                    dcc.Link(
                        label,
                        href=href,
                        className="nav-link sidebar-link"
                        + (" active" if pathname == href else ""),
                    )
                    for label, href in nav_links
                ],
                className="sidebar-nav nav nav-pills flex-column",
            ),
            html.Div(
                [
                    html.Div("Manual tracking, fast validation.", className="sidebar-footnote"),
                    html.Div("Built with Dash + SQLite", className="sidebar-footnote muted"),
                ],
                className="sidebar-footer",
            ),
        ],
        className="sidebar-shell",
    )