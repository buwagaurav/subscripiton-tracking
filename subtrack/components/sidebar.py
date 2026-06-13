from dash import dcc, html


_NAV_ITEMS = [
    ("bi-house",       "Overview",      "/"),
    ("bi-credit-card", "Subscriptions", "/subscriptions"),
    ("bi-bar-chart",   "Analytics",     "/analytics"),
    ("bi-envelope",    "Gmail Import",  "/gmail-import"),
    ("bi-stars",       "SubTrack AI",   "/ai-chat"),
]


def build_sidebar(
    user_name: str | None = None,
    user_email: str | None = None,
    pathname: str = "/",
) -> html.Div:
    name = user_name or "Guest"
    initials = ""
    parts = name.split()
    if parts:
        initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

    nav_links = [
        dcc.Link(
            [
                html.I(className=f"bi {icon}"),
                html.Span(label),
            ],
            href=href,
            className="sidebar-link" + (" active" if pathname == href else ""),
        )
        for icon, label, href in _NAV_ITEMS
    ]

    return html.Div(
        [
            # ── Wordmark ─────────────────────────────────────────────
            html.Div(
                [
                    html.Div("ST", className="sidebar-logo-mark"),
                    html.Span("SubTrack", className="sidebar-brand"),
                ],
                className="sidebar-wordmark",
            ),

            # ── Navigation ───────────────────────────────────────────
            html.Div("Menu", className="sidebar-section"),
            html.Nav(nav_links, className="sidebar-nav-mobile"),

            # ── Bottom user card ─────────────────────────────────────
            html.Div(
                html.Div(
                    [
                        html.Div(initials, className="sidebar-avatar"),
                        html.Div(
                            [
                                html.Div(name, className="sidebar-user-name"),
                                html.Div(user_email or "", className="sidebar-user-email"),
                            ]
                        ),
                    ],
                    className="sidebar-user",
                ),
                className="sidebar-bottom",
            ),
        ],
        className="sidebar-shell",
    )