from __future__ import annotations

from datetime import date, datetime, timedelta

import dash
from dash import Input, Output, State, callback, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash.dash_table.Format import Format, Symbol

from subtrack.auth import current_user
from subtrack.database.db import (
    create_subscription,
    delete_subscription,
    fetch_categories,
    fetch_subscription,
    fetch_subscriptions,
    update_subscription,
)


dash.register_page(__name__, path="/subscriptions", name="Subscriptions")


def _category_options() -> list[dict]:
    return [{"label": c.name, "value": c.id} for c in fetch_categories()]


def _serialize(subscriptions) -> list[dict]:
    today = date.today()
    rows = []
    for item in subscriptions:
        days_until = (item.renewal_date - today).days
        rows.append(
            {
                "id": item.id,
                "name": item.name,
                "category": item.category.name,
                "category_id": item.category_id,
                "cost": round(item.cost, 2),
                "billing_cycle": item.billing_cycle,
                "renewal_date": item.renewal_date.isoformat(),
                "days_until": days_until,
            }
        )
    return rows


def _filter_rows(rows, search_value, category_value, sort_value):
    filtered = rows
    if search_value:
        q = search_value.lower()
        filtered = [
            r for r in filtered
            if q in r["name"].lower()
            or q in r["category"].lower()
            or q in (r.get("notes") or "").lower()
        ]
    if category_value:
        filtered = [r for r in filtered if r["category_id"] == category_value]
    if sort_value == "renewal_asc":
        filtered = sorted(filtered, key=lambda r: r["renewal_date"])
    elif sort_value == "renewal_desc":
        filtered = sorted(filtered, key=lambda r: r["renewal_date"], reverse=True)
    elif sort_value == "cost_asc":
        filtered = sorted(filtered, key=lambda r: r["cost"])
    elif sort_value == "cost_desc":
        filtered = sorted(filtered, key=lambda r: r["cost"], reverse=True)
    return filtered


def _urgency(days: int) -> tuple[str, str]:
    """Return (label, bootstrap color) for the days-left badge."""
    if days <= 0:
        return "Today", "danger"
    if days <= 3:
        return f"{days}d", "danger"
    if days <= 7:
        return f"{days}d", "warning"
    if days <= 30:
        return f"{days}d", "info"
    return f"{days}d", "secondary"


def layout() -> dbc.Container:
    user = current_user()
    rows = _serialize(fetch_subscriptions(user.id)) if user else []
    today = date.today()

    return dbc.Container(
        [
            dcc.Store(id="subscriptions-store", data=rows),
            # ── Header ──────────────────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div("Manage", className="section-kicker"),
                            html.H2("Subscriptions", className="page-title"),
                            html.P(
                                "All your recurring services, sorted by what renews next.",
                                className="page-copy",
                            ),
                        ],
                        md=7,
                    ),
                    dbc.Col(
                        dbc.Button(
                            "+ Add Subscription",
                            id="open-subscription-modal",
                            color="primary",
                            className="action-button",
                        ),
                        md=5,
                        className="d-flex justify-content-md-end align-items-start pt-2",
                    ),
                ],
                className="mb-4 g-3",
            ),
            # ── Renewal-urgency buckets (populated by callback) ──────────
            html.Div(id="renewal-buckets", className="mb-4"),
            # ── Filters ─────────────────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Input(
                            id="subscription-search",
                            placeholder="Search name or category…",
                            type="search",
                        ),
                        md=5,
                    ),
                    dbc.Col(
                        dbc.Select(
                            id="subscription-category-filter",
                            options=[{"label": "All categories", "value": ""}]
                            + _category_options(),
                            value="",
                        ),
                        md=3,
                    ),
                    dbc.Col(
                        dbc.Select(
                            id="subscription-sort",
                            options=[
                                {"label": "Renewal: soonest first", "value": "renewal_asc"},
                                {"label": "Renewal: latest first", "value": "renewal_desc"},
                                {"label": "Cost: low → high", "value": "cost_asc"},
                                {"label": "Cost: high → low", "value": "cost_desc"},
                            ],
                            value="renewal_asc",
                        ),
                        md=4,
                    ),
                ],
                className="g-3 mb-3",
            ),
            # ── Main table + detail panel ────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dash_table.DataTable(
                                    id="subscriptions-table",
                                    columns=[
                                        {"name": "Service", "id": "name"},
                                        {"name": "Category", "id": "category"},
                                        {
                                            "name": "Cost",
                                            "id": "cost",
                                            "type": "numeric",
                                            "format": Format(symbol=Symbol.yes, symbol_prefix="$"),
                                        },
                                        {"name": "Billing", "id": "billing_cycle"},
                                        {"name": "Renewal Date", "id": "renewal_date"},
                                        {"name": "Days Left", "id": "days_until", "type": "numeric"},
                                    ],
                                    data=rows,
                                    row_selectable="single",
                                    selected_rows=[],
                                    page_size=10,
                                    style_as_list_view=True,
                                    style_table={"overflowX": "auto"},
                                    style_header={
                                        "backgroundColor": "#111827",
                                        "border": "1px solid #1f2937",
                                        "color": "#f8fafc",
                                        "fontWeight": "600",
                                    },
                                    style_cell={
                                        "backgroundColor": "#0f172a",
                                        "border": "1px solid #1f2937",
                                        "color": "#cbd5e1",
                                        "padding": "14px",
                                        "fontFamily": "Space Grotesk, sans-serif",
                                    },
                                    style_data_conditional=[
                                        {
                                            "if": {"filter_query": "{days_until} <= 0"},
                                            "backgroundColor": "#3f1d1d",
                                            "color": "#fecaca",
                                        },
                                        {
                                            "if": {
                                                "filter_query": "{days_until} > 0 && {days_until} <= 7"
                                            },
                                            "backgroundColor": "#3d2b10",
                                            "color": "#fed7aa",
                                        },
                                    ],
                                )
                            ),
                            className="panel-card",
                        ),
                        lg=8,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div("Selected Item", className="section-kicker"),
                                    html.H3("Details", className="section-title"),
                                    html.Div(
                                        id="subscription-detail-panel",
                                        className="detail-panel",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    "Edit",
                                                    id="edit-subscription-button",
                                                    color="secondary",
                                                    className="w-100",
                                                )
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    "Delete",
                                                    id="delete-subscription-button",
                                                    color="danger",
                                                    className="w-100",
                                                )
                                            ),
                                        ],
                                        className="g-2 mt-3",
                                    ),
                                ]
                            ),
                            className="panel-card",
                        ),
                        lg=4,
                    ),
                ],
                className="g-4",
            ),
            # ── Hidden id store used by callbacks ────────────────────────
            dbc.Input(id="subscription-id", type="hidden"),
            # ── Add / Edit modal ─────────────────────────────────────────
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(id="subscription-modal-title")),
                    dbc.ModalBody(
                        [
                            dbc.Alert(id="subscription-form-alert", is_open=False, color="danger"),
                            dbc.Label("Subscription Name", className="form-label"),
                            dbc.Input(id="subscription-name", type="text", placeholder="Netflix"),
                            dbc.Label("Category", className="form-label mt-3"),
                            dbc.Select(id="subscription-category", options=_category_options()),
                            dbc.Label("Cost", className="form-label mt-3"),
                            dbc.Input(id="subscription-cost", type="number", min=0, step=0.01),
                            dbc.Label("Billing Cycle", className="form-label mt-3"),
                            dbc.Select(
                                id="subscription-billing-cycle",
                                options=[
                                    {"label": "Monthly", "value": "Monthly"},
                                    {"label": "Yearly", "value": "Yearly"},
                                ],
                                value="Monthly",
                            ),
                            dbc.Label("Renewal Date", className="form-label mt-3"),
                            dbc.Input(
                                id="subscription-renewal-date",
                                type="date",
                                value=today.isoformat(),
                            ),
                            dbc.Label("Notes", className="form-label mt-3"),
                            dbc.Textarea(id="subscription-notes", placeholder="Optional notes"),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button("Cancel", id="close-subscription-modal", color="secondary"),
                            dbc.Button("Save", id="save-subscription-button", color="primary"),
                        ]
                    ),
                ],
                id="subscription-modal",
                is_open=False,
                size="lg",
                centered=True,
            ),
            dbc.Toast(
                id="subscription-toast",
                header="Subscriptions updated",
                is_open=False,
                dismissable=True,
                duration=4000,
                icon="success",
                className="toast-shell",
            ),
        ],
        fluid=True,
        className="page-shell",
    )


@callback(
    Output("subscriptions-store", "data"),
    Output("subscription-toast", "children"),
    Output("subscription-toast", "is_open"),
    Output("subscription-modal", "is_open"),
    Output("subscription-form-alert", "children"),
    Output("subscription-form-alert", "is_open"),
    Input("save-subscription-button", "n_clicks"),
    Input("delete-subscription-button", "n_clicks"),
    State("subscription-id", "value"),
    State("subscription-name", "value"),
    State("subscription-category", "value"),
    State("subscription-cost", "value"),
    State("subscription-billing-cycle", "value"),
    State("subscription-renewal-date", "value"),
    State("subscription-notes", "value"),
    prevent_initial_call=True,
)
def mutate_subscription(
    save_clicks,
    delete_clicks,
    subscription_id,
    name,
    category_id,
    cost,
    billing_cycle,
    renewal_date_value,
    notes,
):
    triggered = dash.ctx.triggered_id
    if triggered is None:
        raise PreventUpdate
    user = current_user()
    if user is None:
        return no_update, "", False, False, "Session expired. Sign in again.", True

    if triggered == "save-subscription-button":
        if not all([name, category_id, cost, billing_cycle, renewal_date_value]):
            return no_update, "", False, True, "All required fields must be filled in.", True
        renewal_date = datetime.strptime(renewal_date_value, "%Y-%m-%d").date()
        if subscription_id:
            updated = update_subscription(
                user.id,
                int(subscription_id),
                name,
                int(category_id),
                float(cost),
                billing_cycle,
                renewal_date,
                notes,
            )
            if not updated:
                return no_update, "", False, True, "Subscription no longer exists.", True
            message = f"{name} updated."
        else:
            create_subscription(
                user.id, name, int(category_id), float(cost), billing_cycle, renewal_date, notes
            )
            message = f"{name} added."
        return _serialize(fetch_subscriptions(user.id)), message, True, False, "", False

    if not subscription_id:
        return no_update, "", False, False, "", False
    if delete_subscription(user.id, int(subscription_id)):
        return _serialize(fetch_subscriptions(user.id)), "Subscription deleted.", True, False, "", False
    return no_update, "", False, False, "", False


@callback(
    Output("subscriptions-table", "data"),
    Output("subscription-detail-panel", "children"),
    Output("renewal-buckets", "children"),
    Output("subscription-id", "value"),
    Input("subscriptions-store", "data"),
    Input("subscription-search", "value"),
    Input("subscription-category-filter", "value"),
    Input("subscription-sort", "value"),
    Input("subscriptions-table", "selected_rows"),
)
def update_view(rows, search, category, sort, selected_rows):
    filtered = _filter_rows(rows or [], search, category, sort)

    # Detail panel
    selected = None
    if filtered and selected_rows:
        idx = selected_rows[0]
        if 0 <= idx < len(filtered):
            selected = filtered[idx]

    if selected is None:
        detail = html.Div("Select a row to inspect.", className="empty-state")
        selected_id = None
    else:
        days = selected["days_until"]
        badge_text, badge_color = _urgency(days)
        detail = html.Div(
            [
                html.H4(selected["name"], className="detail-title"),
                html.Div(selected["category"], className="detail-category"),
                html.Div(
                    f"${selected['cost']:,.2f} · {selected['billing_cycle']}",
                    className="detail-price",
                ),
                html.Div(
                    [
                        html.Span(
                            datetime.strptime(selected["renewal_date"], "%Y-%m-%d").strftime(
                                "%b %d, %Y"
                            ),
                            className="detail-date me-2",
                        ),
                        dbc.Badge(badge_text, color=badge_color),
                    ]
                ),
            ]
        )
        selected_id = selected["id"]

    # Renewal buckets (side-by-side)
    all_rows = rows or []
    buckets = [
        ("Renewing Today", "danger", [r for r in all_rows if r["days_until"] <= 0]),
        ("This Week", "warning", [r for r in all_rows if 0 < r["days_until"] <= 7]),
        ("This Month", "info", [r for r in all_rows if 7 < r["days_until"] <= 30]),
        ("Later", "secondary", [r for r in all_rows if r["days_until"] > 30]),
    ]
    bucket_cols = []
    for label, color, items in buckets:
        names = (
            ", ".join(r["name"] for r in items[:3]) + ("…" if len(items) > 3 else "")
            if items
            else "—"
        )
        bucket_cols.append(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            dbc.Badge(label, color=color, className="mb-2"),
                            html.Div(str(len(items)), className="bucket-count"),
                            html.Div(names, className="bucket-copy"),
                        ]
                    ),
                    className="panel-card bucket-card h-100",
                ),
                xs=6,
                lg=3,
            )
        )
    buckets_row = dbc.Row(bucket_cols, className="g-3")

    return filtered, detail, buckets_row, selected_id


@callback(
    Output("subscription-modal", "is_open", allow_duplicate=True),
    Output("subscription-modal-title", "children"),
    Output("subscription-id", "value", allow_duplicate=True),
    Output("subscription-name", "value"),
    Output("subscription-category", "value"),
    Output("subscription-cost", "value"),
    Output("subscription-billing-cycle", "value"),
    Output("subscription-renewal-date", "value"),
    Output("subscription-notes", "value"),
    Output("subscription-form-alert", "children", allow_duplicate=True),
    Output("subscription-form-alert", "is_open", allow_duplicate=True),
    Input("open-subscription-modal", "n_clicks"),
    Input("edit-subscription-button", "n_clicks"),
    Input("close-subscription-modal", "n_clicks"),
    State("subscription-id", "value"),
    prevent_initial_call=True,
)
def manage_modal(open_clicks, edit_clicks, close_clicks, subscription_id):
    triggered = dash.ctx.triggered_id
    default_cat = _category_options()[0]["value"] if _category_options() else None
    blank = ("", default_cat, None, "Monthly", date.today().isoformat(), "", "", False)

    if triggered == "close-subscription-modal":
        return (False, no_update, None) + blank

    if triggered == "open-subscription-modal":
        return (True, "Add Subscription", None) + blank

    # edit
    if not subscription_id:
        return True, "Edit Subscription", None, *blank[:6], "Select a subscription first.", True

    user = current_user()
    if user is None:
        return True, "Edit Subscription", None, *blank[:6], "Session expired.", True

    sub = fetch_subscription(int(subscription_id), user.id)
    if sub is None:
        return True, "Edit Subscription", None, *blank[:6], "Subscription not found.", True

    return (
        True,
        "Edit Subscription",
        sub.id,
        sub.name,
        sub.category_id,
        sub.cost,
        sub.billing_cycle,
        sub.renewal_date.isoformat(),
        sub.notes or "",
        "",
        False,
    )
