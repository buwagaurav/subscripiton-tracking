from __future__ import annotations

from datetime import date, timedelta

import dash
from dash import Input, Output, callback, dcc, html
import dash_bootstrap_components as dbc

from subtrack.auth import current_user
from subtrack.components.cards import metric_card, renewal_status_badge
from subtrack.database.db import fetch_subscriptions


dash.register_page(__name__, path="/", name="Dashboard")


def _normalize_monthly_cost(cost: float, billing_cycle: str) -> float:
    return cost if billing_cycle == "Monthly" else cost / 12


def _normalize_annual_cost(cost: float, billing_cycle: str) -> float:
    return cost * 12 if billing_cycle == "Monthly" else cost


def _build_alert(subscription_name: str, days_until: int) -> str:
    if days_until == 0:
        return f"{subscription_name} renews today"
    if days_until == 1:
        return f"{subscription_name} renews tomorrow"
    return f"{subscription_name} renews in {days_until} days"


def layout() -> dbc.Container:
    user = current_user()
    subscriptions = fetch_subscriptions(user.id) if user else []
    today = date.today()
    week_end = today + timedelta(days=7)
    monthly_spend = sum(
        _normalize_monthly_cost(item.cost, item.billing_cycle) for item in subscriptions
    )
    annual_spend = sum(
        _normalize_annual_cost(item.cost, item.billing_cycle) for item in subscriptions
    )
    due_this_week = [
        item for item in subscriptions if today <= item.renewal_date <= week_end
    ]

    return dbc.Container(
        [
            dcc.Interval(id="dashboard-refresh", interval=60_000, n_intervals=0),
            dbc.Row(
                [
                    dbc.Col(
                        metric_card(
                            "Monthly Spend",
                            f"${monthly_spend:,.2f}",
                            "Normalized recurring monthly outflow",
                            "teal-accent",
                        ),
                        md=6,
                        xl=3,
                    ),
                    dbc.Col(
                        metric_card(
                            "Annual Spend",
                            f"${annual_spend:,.2f}",
                            "Expected yearly commitment",
                            "amber-accent",
                        ),
                        md=6,
                        xl=3,
                    ),
                    dbc.Col(
                        metric_card(
                            "Active Subscriptions",
                            str(len(subscriptions)),
                            "Tracked recurring services",
                            "rose-accent",
                        ),
                        md=6,
                        xl=3,
                    ),
                    dbc.Col(
                        metric_card(
                            "Due This Week",
                            str(len(due_this_week)),
                            "Renewals that need attention soon",
                            "blue-accent",
                        ),
                        md=6,
                        xl=3,
                    ),
                ],
                className="g-4 mb-4",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div("Dashboard Alerts", className="section-kicker"),
                                    html.H3("Renewal signals", className="section-title"),
                                    html.Div(id="dashboard-alerts"),
                                ]
                            ),
                            className="panel-card panel-tall",
                        ),
                        lg=7,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div("This Month", className="section-kicker"),
                                    html.H3("Upcoming renewals", className="section-title"),
                                    html.Div(id="dashboard-upcoming"),
                                ]
                            ),
                            className="panel-card panel-tall",
                        ),
                        lg=5,
                    ),
                ],
                className="g-4",
            ),
        ],
        fluid=True,
        className="page-shell",
    )


@callback(
    Output("dashboard-alerts", "children"),
    Output("dashboard-upcoming", "children"),
    Input("dashboard-refresh", "n_intervals"),
)
def refresh_dashboard(_: int):
    user = current_user()
    subscriptions = fetch_subscriptions(user.id) if user else []
    today = date.today()
    month_end = today + timedelta(days=30)

    alerts = []
    upcoming = []
    relevant = sorted(
        [item for item in subscriptions if today <= item.renewal_date <= month_end],
        key=lambda item: item.renewal_date,
    )

    for item in relevant[:6]:
        days_until = (item.renewal_date - today).days
        alerts.append(
            dbc.Alert(
                [
                    html.Div(_build_alert(item.name, days_until), className="alert-title"),
                    html.Small(item.category.name, className="alert-subtitle"),
                ],
                color="danger" if days_until <= 1 else "warning" if days_until <= 7 else "secondary",
                className="dashboard-alert",
            )
        )
        upcoming.append(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Div(item.name, className="renewal-item-title"),
                        html.Div(item.renewal_date.strftime("%b %d, %Y"), className="renewal-item-date"),
                        html.Div(
                            [
                                html.Span(f"${item.cost:,.2f}"),
                                html.Span(item.billing_cycle, className="renewal-cycle"),
                            ],
                            className="renewal-item-meta",
                        ),
                        renewal_status_badge(days_until),
                    ]
                ),
                className="renewal-item-card",
            )
        )

    if not alerts:
        alerts = [html.Div("No renewals due in the next 30 days.", className="empty-state")]
    if not upcoming:
        upcoming = [html.Div("No upcoming renewals in this window.", className="empty-state")]

    return alerts, upcoming
