from __future__ import annotations

from datetime import date, timedelta

import dash
from dash import Input, Output, callback, dcc, html
import dash_bootstrap_components as dbc

from subtrack.auth import current_user
from subtrack.components.cards import (
    metric_card,
    renewal_status_badge,
    service_avatar,
    service_color,
    service_initial,
)
from subtrack.database.db import fetch_subscriptions


dash.register_page(__name__, path="/", name="Dashboard")


def _monthly(cost: float, cycle: str) -> float:
    return cost if cycle == "Monthly" else cost / 12


def _annual(cost: float, cycle: str) -> float:
    return cost * 12 if cycle == "Monthly" else cost


def layout() -> dbc.Container:
    user = current_user()
    subscriptions = fetch_subscriptions(user.id) if user else []
    today = date.today()
    week_end = today + timedelta(days=7)

    monthly_spend = sum(_monthly(s.cost, s.billing_cycle) for s in subscriptions)
    annual_spend  = sum(_annual(s.cost, s.billing_cycle)  for s in subscriptions)
    due_this_week = [s for s in subscriptions if today <= s.renewal_date <= week_end]

    return dbc.Container(
        [
            dcc.Interval(id="dashboard-refresh", interval=60_000, n_intervals=0),

            # ── Page header ──────────────────────────────────────────
            html.Div(
                [
                    html.Div("Overview", className="page-kicker"),
                    html.H1("Dashboard", className="page-title"),
                    html.P(
                        "Your subscription spend and upcoming renewals at a glance.",
                        className="page-copy",
                    ),
                ],
                className="page-header",
            ),

            # ── Metric cards ─────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        metric_card("Monthly Spend", f"${monthly_spend:,.2f}",
                                    "Normalized monthly outflow", "teal-accent",
                                    "bi-currency-dollar"),
                        xs=6, xl=3, className="mb-3",
                    ),
                    dbc.Col(
                        metric_card("Annual Spend", f"${annual_spend:,.2f}",
                                    "Projected yearly commitment", "amber-accent",
                                    "bi-calendar3"),
                        xs=6, xl=3, className="mb-3",
                    ),
                    dbc.Col(
                        metric_card("Active Plans", str(len(subscriptions)),
                                    "Tracked recurring services", "blue-accent",
                                    "bi-stack"),
                        xs=6, xl=3, className="mb-3",
                    ),
                    dbc.Col(
                        metric_card("Due This Week", str(len(due_this_week)),
                                    "Renewals needing attention", "rose-accent",
                                    "bi-bell"),
                        xs=6, xl=3, className="mb-3",
                    ),
                ],
                className="g-3 mb-2",
            ),

            # ── Renewals + Alerts ─────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div("Next 30 days", className="section-kicker"),
                                    html.H3("Upcoming renewals", className="section-title"),
                                    html.Div(id="dashboard-upcoming"),
                                ]
                            ),
                            className="panel-card panel-tall",
                        ),
                        lg=7,
                        className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div("Needs attention", className="section-kicker"),
                                    html.H3("Renewal alerts", className="section-title"),
                                    html.Div(id="dashboard-alerts"),
                                ]
                            ),
                            className="panel-card panel-tall",
                        ),
                        lg=5,
                        className="mb-3",
                    ),
                ],
                className="g-3",
            ),
        ],
        fluid=True,
        className="page-shell",
    )


@callback(
    Output("dashboard-alerts",   "children"),
    Output("dashboard-upcoming", "children"),
    Input("dashboard-refresh",   "n_intervals"),
)
def refresh_dashboard(_: int):
    user = current_user()
    subscriptions = fetch_subscriptions(user.id) if user else []
    today     = date.today()
    month_end = today + timedelta(days=30)

    relevant = sorted(
        [s for s in subscriptions if today <= s.renewal_date <= month_end],
        key=lambda s: s.renewal_date,
    )

    # ── Alert list ────────────────────────────────────────────────────────
    alerts = []
    for item in relevant[:8]:
        days = (item.renewal_date - today).days
        if days > 7:
            continue
        if days == 0:
            msg = f"{item.name} renews today"
        elif days == 1:
            msg = f"{item.name} renews tomorrow"
        else:
            msg = f"{item.name} renews in {days} days"

        color = "danger" if days <= 1 else "warning"
        alerts.append(
            dbc.Alert(
                [
                    html.Div(msg, className="alert-title"),
                    html.Small(f"${item.cost:,.2f} · {item.billing_cycle}",
                               className="text-muted"),
                ],
                color=color,
                className="dashboard-alert",
            )
        )

    if not alerts:
        alerts = [
            html.Div(
                [
                    html.Div("✓", className="empty-state-icon"),
                    html.Div("No urgent renewals", className="empty-state-text"),
                    html.P("Nothing due in the next 7 days.", className="empty-state-sub"),
                ],
                className="empty-state",
            )
        ]

    # ── Upcoming timeline ─────────────────────────────────────────────────
    upcoming = []
    for item in relevant[:10]:
        days = (item.renewal_date - today).days
        color = service_color(item.name)
        initial = service_initial(item.name)
        upcoming.append(
            html.Div(
                [
                    html.Div(initial, className="renewal-item-avatar",
                             style={"background": color}),
                    html.Div(
                        [
                            html.Div(item.name, className="renewal-item-name"),
                            html.Div(
                                item.renewal_date.strftime("%b %d, %Y"),
                                className="renewal-item-date",
                            ),
                        ],
                        className="renewal-item-info",
                    ),
                    html.Div(
                        [
                            html.Div(f"${item.cost:,.2f}", className="renewal-item-cost"),
                            renewal_status_badge(days),
                        ],
                        className="renewal-item-right",
                    ),
                ],
                className="renewal-item",
            )
        )

    if not upcoming:
        upcoming = [
            html.Div(
                [
                    html.Div("📅", className="empty-state-icon"),
                    html.Div("No renewals this month", className="empty-state-text"),
                    html.P("All caught up for the next 30 days.", className="empty-state-sub"),
                ],
                className="empty-state",
            )
        ]

    return alerts, upcoming