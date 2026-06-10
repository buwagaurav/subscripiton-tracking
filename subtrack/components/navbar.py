from dash import html


def build_navbar(user_name: str | None = None) -> html.Div:
    initials = ""
    if user_name:
        parts = user_name.split()
        initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

    return html.Div(
        html.Div(
            [
                html.Button(
                    [
                        html.I(className="bi bi-moon"),
                        html.I(className="bi bi-sun"),
                    ],
                    id="theme-toggle-btn",
                    className="notif-btn theme-toggle-btn",
                    title="Toggle dark mode",
                    n_clicks=0,
                    style={"cursor": "pointer"},
                ),
                html.A(
                    [
                        html.I(className="bi bi-bell"),
                        html.Span(
                            id="notif-badge",
                            className="notif-badge",
                            style={"display": "none"},
                        ),
                    ],
                    href="/notifications",
                    className="notif-btn",
                    title="Notifications",
                ),
                html.Div(
                    [
                        html.Div(initials, className="nav-user-avatar"),
                        html.Span(user_name or "", className="d-none d-md-inline",
                                  style={"fontSize": "0.775rem", "fontWeight": "500",
                                         "color": "var(--text-2)"}),
                    ],
                    className="nav-user-chip",
                ) if user_name else html.Span(),
                html.A("Sign out", href="/do-logout", className="logout-btn"),
            ],
            className="nav-actions",
        ),
        className="top-navbar",
    )