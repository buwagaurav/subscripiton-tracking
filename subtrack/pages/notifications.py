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
    "after_renewal": "Paid",
}

_TYPE_STYLES = {
    "7_days":        ("var(--blue-dim)",  "var(--blue)",       "bi-clock"),
    "1_day":         ("var(--amber-dim)", "var(--amber-text)", "bi-exclamation-triangle"),
    "renewal_day":   ("var(--red-dim)",   "var(--red-text)",   "bi-bell"),
    "after_renewal": ("var(--green-dim)", "var(--green-text)", "bi-check-circle"),
}


def layout() -> dbc.Container:
    return dbc.Container(
        [
            html.Div(id="notif-page-trigger", style={"display": "none"}),
            dbc.Row(
                dbc.Col(
                    [
                        html.Div("Alerts", className="page-kicker"),
                        html.H1("Notifications", className="page-title"),
                        html.P(
                            "Renewal reminders and payment confirmations for your subscriptions.",
                            className="page-copy",
                        ),
                        html.Div(id="notif-page-content", className="mt-4"),
                    ],
                    lg=10, xl=8,
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
                html.Div("✓", className="empty-state-icon"),
                html.Div("All caught up", className="empty-state-text"),
                html.P("No notifications — your subscriptions are on track.", className="empty-state-sub"),
            ],
            className="empty-state py-5",
        )

    items = []
    for n in notifications:
        icon_str = _NOTIFICATION_ICONS.get(n.notification_type, "🔔")
        label    = _TYPE_LABELS.get(n.notification_type, n.notification_type)
        bg, fg, bi_icon = _TYPE_STYLES.get(
            n.notification_type, ("var(--blue-dim)", "var(--blue)", "bi-bell")
        )

        items.append(
            html.Div(
                [
                    html.Div(
                        html.I(className=f"bi {bi_icon}"),
                        className="notif-icon-wrap",
                        style={"background": bg, "color": fg},
                    ),
                    html.Div(
                        [
                            html.Div(n.message, className="notif-message",
                                     style={"fontWeight": "600" if not n.is_read else "500"}),
                            html.Div(
                                [
                                    html.Span(
                                        label,
                                        style={
                                            "background": bg,
                                            "color": fg,
                                            "padding": "0.1rem 0.45rem",
                                            "borderRadius": "99px",
                                            "fontSize": "0.68rem",
                                            "fontWeight": "600",
                                        },
                                    ),
                                    html.Span(
                                        n.renewal_date.strftime("%b %d, %Y"),
                                        style={"color": "var(--text-3)", "fontSize": "0.72rem"},
                                    ),
                                ],
                                className="notif-meta",
                            ),
                        ],
                        className="notif-body",
                    ),
                ],
                className="notif-row" + ("" if n.is_read else " unread"),
            )
        )
    return html.Div(items)


@callback(
    Output("notif-page-content", "children"),
    Input("notif-page-trigger",  "children"),
)
def load_notifications(_):
    user = current_user()
    if user is None:
        return html.Div()

    generate_notifications(user.id)
    notifications  = get_notifications(user.id)
    unread_count   = sum(1 for n in notifications if not n.is_read)

    header = html.Div(
        [
            html.Span(
                f"{unread_count} unread" if unread_count else "All caught up",
                style={"fontSize": "0.85rem", "color": "var(--text-2)", "fontWeight": "500"},
            ),
            dbc.Button(
                [html.I(className="bi bi-check2-all me-1"), "Mark all read"],
                id="mark-all-read-btn",
                color="secondary",
                size="sm",
                outline=True,
                disabled=(unread_count == 0),
                style={"marginLeft": "1rem"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "marginBottom": "1.25rem"},
    )

    return [header, _render_notifications(notifications)]


@callback(
    Output("notif-page-content", "children", allow_duplicate=True),
    Input("mark-all-read-btn",   "n_clicks"),
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
            html.Span(
                "All caught up",
                style={"fontSize": "0.85rem", "color": "var(--text-2)", "fontWeight": "500"},
            ),
            dbc.Button(
                [html.I(className="bi bi-check2-all me-1"), "Mark all read"],
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