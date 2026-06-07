from __future__ import annotations

from datetime import date

import dash
from dash import Input, Output, callback, dcc, html
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


def _empty_figure(title: str):
    fig = px.scatter(title=title)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[{"text": "No data available", "xref": "paper", "yref": "paper", "showarrow": False}],
    )
    return fig


def layout() -> dbc.Container:
    return dbc.Container(
        [
            dcc.Interval(id="analytics-refresh", interval=60_000, n_intervals=0),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div("Insights", className="section-kicker"),
                            html.H2("Spend analytics", className="page-title"),
                            html.P(
                                "Quick visibility into where subscription money goes and what renews next.",
                                className="page-copy",
                            ),
                        ],
                        lg=8,
                    )
                ],
                className="mb-4",
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
)
def refresh_analytics(_: int):
    df = _build_dataframe()
    if df.empty:
        return (
            _empty_figure("Spend by Category"),
            _empty_figure("Monthly Cost Breakdown"),
            _empty_figure("Upcoming Renewals Timeline"),
        )

    category_summary = df.groupby("category", as_index=False)["monthly_cost"].sum()
    pie = px.pie(
        category_summary,
        names="category",
        values="monthly_cost",
        hole=0.55,
        title="Spend by Category",
        color_discrete_sequence=["#2dd4bf", "#f59e0b", "#38bdf8", "#fb7185", "#818cf8", "#22c55e"],
    )

    bar = px.bar(
        df.sort_values("monthly_cost", ascending=False),
        x="name",
        y="monthly_cost",
        color="category",
        title="Monthly Cost Breakdown",
        color_discrete_sequence=["#2dd4bf", "#f59e0b", "#38bdf8", "#fb7185", "#818cf8", "#22c55e"],
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
        title="Upcoming Renewals Timeline",
        color_discrete_sequence=["#2dd4bf", "#f59e0b", "#38bdf8", "#fb7185", "#818cf8", "#22c55e"],
    )
    timeline.update_yaxes(autorange="reversed")

    for figure in [pie, bar, timeline]:
        figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="#111827",
            plot_bgcolor="#111827",
            font={"family": "Space Grotesk, sans-serif", "color": "#e2e8f0"},
            margin={"l": 20, "r": 20, "t": 56, "b": 20},
            legend={"orientation": "h", "yanchor": "bottom", "y": -0.25, "xanchor": "center", "x": 0.5},
        )

    bar.update_xaxes(title=None)
    bar.update_yaxes(title="USD / month")
    timeline.update_xaxes(title=None)
    timeline.update_yaxes(title=None)
    pie.update_traces(textinfo="label+percent")

    return pie, bar, timeline
