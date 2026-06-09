from __future__ import annotations

from datetime import date, timedelta

import dash
from dash import Input, Output, MATCH, State, callback, dcc, html
import dash_bootstrap_components as dbc

from subtrack.auth import current_user
from subtrack.database.db import create_subscription, fetch_categories
from subtrack import gmail


dash.register_page(__name__, path="/gmail-import", name="Gmail Import")


def layout() -> dbc.Container:
    user = current_user()
    if user is None:
        return html.Div("Please log in first.")

    if not gmail.is_configured():
        return _unconfigured_layout()

    connected = bool(user.google_refresh_token)
    return _connected_layout() if connected else _disconnected_layout()


def _unconfigured_layout() -> dbc.Container:
    return dbc.Container(
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div("Gmail Import", className="section-kicker"),
                            html.H3("Gmail credentials not configured", className="section-title"),
                            html.P(
                                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to enable this feature.",
                                className="page-copy",
                            ),
                            dbc.Alert(
                                [
                                    html.Strong("Setup steps: "),
                                    html.Ol(
                                        [
                                            html.Li("Create a project at console.cloud.google.com"),
                                            html.Li("Enable the Gmail API"),
                                            html.Li(
                                                [
                                                    "Create OAuth 2.0 credentials (Web application) and add ",
                                                    html.Code("http://localhost:8050/auth/google/callback"),
                                                    " as an authorized redirect URI",
                                                ]
                                            ),
                                            html.Li(
                                                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET as environment variables"
                                            ),
                                        ]
                                    ),
                                ],
                                color="warning",
                            ),
                        ]
                    ),
                    className="panel-card",
                ),
                md=8,
            ),
            className="justify-content-center mt-4",
        ),
        fluid=True,
        className="page-shell",
    )


def _disconnected_layout() -> dbc.Container:
    return dbc.Container(
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div("Gmail Import", className="section-kicker"),
                            html.H3("Connect your Gmail", className="section-title"),
                            html.P(
                                "SubTrack scans your inbox for subscription receipts and renewal "
                                "notices, then suggests what to add to your tracker. "
                                "Access is read-only — SubTrack never reads personal email or sends messages.",
                                className="page-copy mb-3",
                            ),
                            html.Ul(
                                [
                                    html.Li("Searches the last 12 months of your inbox"),
                                    html.Li("Detects 35+ popular services automatically"),
                                    html.Li("Read-only Gmail access — no sending or modifying"),
                                    html.Li("You review and approve every detected subscription"),
                                ],
                                className="mb-4",
                            ),
                            html.A(
                                dbc.Button(
                                    "Connect Gmail",
                                    color="primary",
                                    size="lg",
                                    className="me-3",
                                ),
                                href="/auth/google",
                            ),
                        ]
                    ),
                    className="panel-card",
                ),
                md=7,
            ),
            className="justify-content-center mt-4",
        ),
        fluid=True,
        className="page-shell",
    )


def _connected_layout() -> dbc.Container:
    return dbc.Container(
        [
            dcc.Store(id="gmail-scan-results", storage_type="memory"),
            dbc.Row(
                dbc.Col(
                    [
                        html.Div("Gmail Import", className="section-kicker"),
                        html.H2("Inbox scanner", className="section-title"),
                        html.P(
                            "Scan your Gmail inbox for subscription receipts. "
                            "Review the results and add what you want to track.",
                            className="page-copy",
                        ),
                    ]
                ),
                className="mb-4",
            ),
            dbc.Row(
                dbc.Col(
                    [
                        dbc.Button(
                            "Scan Inbox",
                            id="gmail-scan-btn",
                            color="primary",
                            className="me-3",
                        ),
                        html.A(
                            "Disconnect Gmail",
                            href="/auth/google/disconnect",
                            className="btn btn-outline-secondary btn-sm",
                        ),
                    ]
                ),
                className="mb-3",
            ),
            dbc.Row(
                dbc.Col(
                    html.Div(id="gmail-scan-status", className="text-muted small mb-2")
                )
            ),
            dcc.Loading(
                html.Div(id="gmail-results-area"),
                type="circle",
            ),
        ],
        fluid=True,
        className="page-shell",
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@callback(
    Output("gmail-scan-results", "data"),
    Output("gmail-scan-status", "children"),
    Input("gmail-scan-btn", "n_clicks"),
    prevent_initial_call=True,
)
def run_scan(_: int):
    user = current_user()
    if user is None:
        return [], "Not authenticated."
    results = gmail.scan_inbox(user.id)
    if not results:
        return [], "No subscription signals found. Your inbox may not have receipts matching known services, or the scan permissions may need refreshing."
    return results, f"Found {len(results)} subscription signal(s) — review and add the ones you want to track."


@callback(
    Output("gmail-results-area", "children"),
    Input("gmail-scan-results", "data"),
)
def render_results(scan_data: list | None):
    if not scan_data:
        return html.Div(
            "Click 'Scan Inbox' to search for subscription emails.",
            className="empty-state",
        )

    cards = []
    for i, item in enumerate(scan_data):
        amount_display = f"${item['amount']:,.2f}" if item.get("amount") else "Amount unknown"
        cards.append(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Div(item.get("category", ""), className="section-kicker"),
                            html.H5(item["name"], className="mb-1"),
                            html.Div(
                                [
                                    html.Span(amount_display, className="me-2"),
                                    dbc.Badge(
                                        item.get("billing_cycle", "Monthly"),
                                        color="secondary",
                                    ),
                                ],
                                className="mb-2",
                            ),
                            html.Small(
                                f"Detected from: {item.get('subject', '')[:70]}",
                                className="text-muted d-block mb-3",
                            ),
                            dbc.Button(
                                "Add to SubTrack",
                                id={"type": "gmail-add-btn", "index": i},
                                color="primary",
                                size="sm",
                                n_clicks=0,
                            ),
                            html.Div(
                                id={"type": "gmail-add-status", "index": i},
                                className="mt-2 small",
                            ),
                        ]
                    ),
                    className="panel-card h-100",
                ),
                md=4,
                className="mb-4",
            )
        )

    return dbc.Row(cards)


@callback(
    Output({"type": "gmail-add-status", "index": MATCH}, "children"),
    Input({"type": "gmail-add-btn", "index": MATCH}, "n_clicks"),
    State("gmail-scan-results", "data"),
    State({"type": "gmail-add-btn", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def add_from_gmail(n_clicks: int, scan_data: list | None, btn_id: dict):
    if not n_clicks or not scan_data:
        return ""
    user = current_user()
    if user is None:
        return dbc.Alert("Not authenticated.", color="danger", className="py-1 px-2 mb-0")

    idx = btn_id["index"]
    if idx >= len(scan_data):
        return ""

    item = scan_data[idx]
    categories = {cat.name: cat.id for cat in fetch_categories()}
    category_id = (
        categories.get(item.get("category", ""))
        or categories.get("Streaming")
        or next(iter(categories.values()), 1)
    )
    cost = item.get("amount") or 0.0
    renewal_date = date.today() + timedelta(days=30)

    try:
        create_subscription(
            user_id=user.id,
            name=item["name"],
            category_id=category_id,
            cost=cost,
            billing_cycle=item.get("billing_cycle", "Monthly"),
            renewal_date=renewal_date,
            notes=f"Imported via Gmail — {item.get('subject', '')[:100]}",
        )
        return dbc.Alert("Added!", color="success", className="py-1 px-2 mb-0")
    except Exception:
        return dbc.Alert(
            "Could not add — it may already exist.",
            color="warning",
            className="py-1 px-2 mb-0",
        )
