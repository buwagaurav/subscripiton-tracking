from __future__ import annotations

from datetime import date

import dash
from dash import Input, Output, callback, dcc, html, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

from subtrack.auth import current_user
from subtrack.database.db import fetch_subscriptions


dash.register_page(__name__, path="/analytics", name="Analytics")


def _build_dataframe() -> pd.DataFrame:
    rows = []
    user = current_user()
    subscriptions = fetch_subscriptions(user.id) if user else []
    for item in subscriptions:
        monthly_cost = item.cost if item.billing_cycle == "Monthly" else item.cost / 12
        rows.append(
            {
                "name": item.name,
                "category": item.category.name,
                "cost": item.cost,
                "monthly_cost": round(monthly_cost, 2),
                "billing_cycle": item.billing_cycle,
                "renewal_date": item.renewal_date,
            }
        )
    return pd.DataFrame(rows)


def _chart_layout(is_dark: bool) -> dict:
    return {
        "template":      "plotly_dark" if is_dark else "plotly_white",
        "paper_bgcolor": "#18181b" if is_dark else "#ffffff",
        "plot_bgcolor":  "#1e1e22" if is_dark else "#fafafa",
        "font": {
            "family": "Inter, -apple-system, sans-serif",
            "color":  "#fafafa" if is_dark else "#18181b",
            "size":   12,
        },
        "margin": {"l": 20, "r": 20, "t": 48, "b": 20},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": -0.3,
                   "xanchor": "center", "x": 0.5},
        "title_font": {
            "family": "Space Grotesk, sans-serif",
            "size":   15,
            "color":  "#fafafa" if is_dark else "#18181b",
        },
    }


def _empty_figure(title: str, is_dark: bool = False):
    fig = px.scatter(title=title)
    fig.update_layout(
        **_chart_layout(is_dark),
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[{
            "text": "No data yet",
            "xref": "paper", "yref": "paper",
            "showarrow": False,
            "font": {"color": "#71717a" if is_dark else "#a1a1aa", "size": 14},
        }],
    )
    return fig


def layout() -> dbc.Container:
    return dbc.Container(
        [
            dcc.Interval(id="analytics-refresh", interval=60_000, n_intervals=0),
            html.Div(
                [
                    html.Div("Insights", className="page-kicker"),
                    html.H2("Spend Analytics", className="page-title"),
                    html.P(
                        "Where your subscription money goes and what renews next.",
                        className="page-copy",
                    ),
                ],
                className="page-header",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(dcc.Graph(id="category-pie-chart", config={"displayModeBar": False})),
                            className="panel-card chart-card",
                        ),
                        lg=4,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(dcc.Graph(id="monthly-bar-chart", config={"displayModeBar": False})),
                            className="panel-card chart-card",
                        ),
                        lg=4,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(dcc.Graph(id="renewals-timeline-chart", config={"displayModeBar": False})),
                            className="panel-card chart-card",
                        ),
                        lg=4,
                    ),
                ],
                className="g-4",
            ),
        ],
        fluid=True,
        className="page-shell",
    )


@callback(
    Output("category-pie-chart", "figure"),
    Output("monthly-bar-chart", "figure"),
    Output("renewals-timeline-chart", "figure"),
    Input("analytics-refresh", "n_intervals"),
    Input("theme-store", "data"),
)
def refresh_analytics(_: int, theme: str | None):
    is_dark = theme == "dark"
    df = _build_dataframe()
    if df.empty:
        return (
            _empty_figure("Spend by Category", is_dark),
            _empty_figure("Monthly Cost Breakdown", is_dark),
            _empty_figure("Upcoming Renewals Timeline", is_dark),
        )

    _PALETTE = ["#6366f1", "#f59e0b", "#3b82f6", "#ef4444", "#8b5cf6", "#10b981"]

    category_summary = df.groupby("category", as_index=False)["monthly_cost"].sum()
    pie = px.pie(
        category_summary,
        names="category",
        values="monthly_cost",
        hole=0.58,
        title="Spend by Category",
        color_discrete_sequence=_PALETTE,
    )

    bar = px.bar(
        df.sort_values("monthly_cost", ascending=False),
        x="name",
        y="monthly_cost",
        color="category",
        title="Monthly Cost Breakdown",
        color_discrete_sequence=_PALETTE,
    )

    timeline_df = df.copy()
    timeline_df["renewal_date"] = pd.to_datetime(timeline_df["renewal_date"])
    timeline_df["start_date"] = timeline_df["renewal_date"] - pd.to_timedelta(2, unit="D")
    timeline = px.timeline(
        timeline_df.sort_values("renewal_date"),
        x_start="start_date",
        x_end="renewal_date",
        y="name",
        color="category",
        title="Upcoming Renewals",
        color_discrete_sequence=_PALETTE,
    )
    timeline.update_yaxes(autorange="reversed")

    layout = _chart_layout(is_dark)
    for figure in [pie, bar, timeline]:
        figure.update_layout(**layout)

    grid_color = "#27272a" if is_dark else "#f0f0f0"
    bar.update_xaxes(title=None, showgrid=False)
    bar.update_yaxes(title="USD / mo", gridcolor=grid_color)
    timeline.update_xaxes(title=None)
    timeline.update_yaxes(title=None)
    pie.update_traces(textinfo="label+percent", textfont_size=11)

    return pie, bar, timeline
