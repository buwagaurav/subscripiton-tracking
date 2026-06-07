from dash import html
import dash_bootstrap_components as dbc


def metric_card(title: str, value: str, helper: str, accent_class: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(title, className="metric-label"),
                html.Div(value, className="metric-value"),
                html.Div(helper, className="metric-helper"),
            ]
        ),
        className=f"metric-card {accent_class}",
    )


def renewal_status_badge(days_until: int) -> dbc.Badge:
    if days_until <= 1:
        color = "danger"
        label = "Urgent"
    elif days_until <= 7:
        color = "warning"
        label = "Soon"
    else:
        color = "info"
        label = "Planned"
    return dbc.Badge(label, color=color, pill=True, className="status-badge")
