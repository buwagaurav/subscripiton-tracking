from __future__ import annotations

import dash
from dash import Input, Output, callback, html
import dash_bootstrap_components as dbc

from subtrack.auth import current_user
from subtrack.database.db import (
    _NOTIFICATION_ICONS,
    generate_notifications,
    get_notifications,
    mark_all_notifications_read,
)


dash.register_page(__name__, path="/notifications", name="Notifications")

_TYPE_LABELS = {
    "7_days":        "7 days before",
    "1_day":         "1 day before",
    "renewal_day":   "Renewal day",
    "after_renewal": "After renewal",
}

_TYPE_COLORS = {
    "7_days":        "#4a9eff",
    "1_day":         "#f5a623",
    "renewal_day":   "#e74c3c",
    "after_renewal": "#2ecc71",
}


def layout() -> dbc.Container:
    return dbc.Container(
        [
            html.Div(id="notif-page-trigger", style={"display": "none"}),
            dbc.Row(
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.Div("Alerts", className="section-kicker"),
                                html.H1("Notifications", className="page-title"),
                            ]
                        ),
                        html.Div(id="notif-page-content"),
                    ],
                    lg=10,
                    xl=8,
                ),
                className="justify-content-center",
            ),
        ],
        fluid=True,
        className="page-shell",
    )


def _render_notifications(notifications):
    if not notifications:
        return html.Div(
            [
                html.Div("🎉", style={"fontSize": "3rem", "marginBottom": "0.5rem"}),
                html.P("No notifications — all subscriptions are on track.", className="text-muted"),
            ],
            className="text-center py-5",
        )

    items = []
    for n in notifications:
        icon = _NOTIFICATION_ICONS.get(n.notification_type, "🔔")
        color = _TYPE_COLORS.get(n.notification_type, "#888")
        label = _TYPE_LABELS.get(n.notification_type, n.notification_type)
        unread_style = {} if n.is_read else {"borderLeft": f"3px solid {color}", "background": "rgba(255,255,255,0.04)"}

        items.append(
            dbc.Card(
                dbc.CardBody(
                    html.Div(
                        [
                            html.Span(icon, style={"fontSize": "1.4rem", "marginRight": "0.75rem", "flexShrink": 0}),
                            html.Div(
                                [
                                    html.Div(n.message, style={"fontWeight": "500" if not n.is_read else "400"}),
                                    html.Div(
                                        [
                                            dbc.Badge(label, style={"background": color, "marginRight": "0.5rem"}),
                                            html.Span(
                                                n.renewal_date.strftime("%b %d, %Y"),
                                                className="text-muted",
                                                style={"fontSize": "0.8rem"},
                                            ),
                                        ],
                                        style={"marginTop": "0.25rem"},
                                    ),
                                ],
                                style={"flex": 1},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    )
                ),
                className="mb-2",
                style={"border": "1px solid rgba(255,255,255,0.1)", **unread_style},
            )
        )
    return html.Div(items)


@callback(
    Output("notif-page-content", "children"),
    Input("notif-page-trigger", "children"),
)
def load_notifications(_):
    user = current_user()
    if user is None:
        return html.Div()

    generate_notifications(user.id)
    notifications = get_notifications(user.id)
    unread_count = sum(1 for n in notifications if not n.is_read)

    header = html.Div(
        [
            html.Span(
                f"{unread_count} unread" if unread_count else "All caught up",
                className="text-muted",
                style={"fontSize": "0.9rem"},
            ),
            dbc.Button(
                "Mark all as read",
                id="mark-all-read-btn",
                color="secondary",
                size="sm",
                outline=True,
                disabled=unread_count == 0,
                style={"marginLeft": "1rem"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "marginBottom": "1.25rem"},
    )

    return [header, _render_notifications(notifications)]


@callback(
    Output("notif-page-content", "children", allow_duplicate=True),
    Input("mark-all-read-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_mark_all_read(_):
    user = current_user()
    if user is None:
        return dash.no_update

    mark_all_notifications_read(user.id)
    notifications = get_notifications(user.id)

    header = html.Div(
        [
            html.Span("All caught up", className="text-muted", style={"fontSize": "0.9rem"}),
            dbc.Button(
                "Mark all as read",
                id="mark-all-read-btn",
                color="secondary",
                size="sm",
                outline=True,
                disabled=True,
                style={"marginLeft": "1rem"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "marginBottom": "1.25rem"},
    )
    return [header, _render_notifications(notifications)]