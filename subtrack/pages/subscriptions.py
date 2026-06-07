from __future__ import annotations

from datetime import date, datetime, timedelta

import dash
from dash import Input, Output, State, callback, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

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
    return [{"label": category.name, "value": category.id} for category in fetch_categories()]


def _serialize(subscriptions):
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
                "notes": item.notes or "",
                "days_until": days_until,
            }
        )
    return rows


def _filter_rows(rows, search_value, category_value, sort_value):
    filtered = rows
    if search_value:
        search_term = search_value.strip().lower()
        filtered = [
            row
            for row in filtered
            if search_term in row["name"].lower()
            or search_term in row["category"].lower()
            or search_term in row["notes"].lower()
        ]
    if category_value:
        filtered = [row for row in filtered if row["category_id"] == category_value]

    if sort_value == "renewal_asc":
        filtered = sorted(filtered, key=lambda row: row["renewal_date"])
    elif sort_value == "renewal_desc":
        filtered = sorted(filtered, key=lambda row: row["renewal_date"], reverse=True)
    elif sort_value == "cost_asc":
        filtered = sorted(filtered, key=lambda row: row["cost"])
    elif sort_value == "cost_desc":
        filtered = sorted(filtered, key=lambda row: row["cost"], reverse=True)
    return filtered


def _renewal_bucket_label(days_until: int) -> str:
    if days_until <= 0:
        return "Renewing Today"
    if days_until <= 7:
        return "Renewing This Week"
    if days_until <= 30:
        return "Renewing This Month"
    return "Later"


def layout() -> dbc.Container:
    user = current_user()
    rows = _serialize(fetch_subscriptions(user.id)) if user else []
    return dbc.Container(
        [
            dcc.Store(id="subscriptions-store", data=rows),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div("Manage", className="section-kicker"),
                            html.H2("Subscriptions", className="page-title"),
                            html.P(
                                "Track recurring products, services, and memberships in one place.",
                                className="page-copy",
                            ),
                        ],
                        md=7,
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Add Subscription",
                            id="open-subscription-modal",
                            color="primary",
                            className="action-button",
                        ),
                        md=5,
                        className="d-flex justify-content-md-end align-items-start",
                    ),
                ],
                className="mb-4 g-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Input(
                                                    id="subscription-search",
                                                    placeholder="Search name, category, notes",
                                                    type="search",
                                                ),
                                                md=5,
                                            ),
                                            dbc.Col(
                                                dbc.Select(
                                                    id="subscription-category-filter",
                                                    options=[
                                                        {"label": "All categories", "value": ""}
                                                    ]
                                                    + _category_options(),
                                                    value="",
                                                ),
                                                md=3,
                                            ),
                                            dbc.Col(
                                                dbc.Select(
                                                    id="subscription-sort",
                                                    options=[
                                                        {
                                                            "label": "Renewal date: soonest",
                                                            "value": "renewal_asc",
                                                        },
                                                        {
                                                            "label": "Renewal date: latest",
                                                            "value": "renewal_desc",
                                                        },
                                                        {"label": "Cost: low to high", "value": "cost_asc"},
                                                        {"label": "Cost: high to low", "value": "cost_desc"},
                                                    ],
                                                    value="renewal_asc",
                                                ),
                                                md=4,
                                            ),
                                        ],
                                        className="g-3 mb-3",
                                    ),
                                    dash_table.DataTable(
                                        id="subscriptions-table",
                                        columns=[
                                            {"name": "Name", "id": "name"},
                                            {"name": "Category", "id": "category"},
                                            {"name": "Cost", "id": "cost", "type": "numeric"},
                                            {"name": "Billing", "id": "billing_cycle"},
                                            {"name": "Renewal Date", "id": "renewal_date"},
                                        ],
                                        data=rows,
                                        row_selectable="single",
                                        selected_rows=[],
                                        page_size=8,
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
                                                "if": {
                                                    "filter_query": "{renewal_date} = '" + date.today().isoformat() + "'"
                                                },
                                                "backgroundColor": "#3f1d1d",
                                                "color": "#fecaca",
                                            }
                                        ],
                                    ),
                                ]
                            ),
                            className="panel-card",
                        ),
                        lg=8,
                    ),
                    dbc.Col(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div("Selected Item", className="section-kicker"),
                                        html.H3("Subscription details", className="section-title"),
                                        html.Div(id="subscription-detail-panel", className="detail-panel"),
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
                                className="panel-card mb-4",
                            ),
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div("Upcoming Renewals", className="section-kicker"),
                                        html.H3("Priority buckets", className="section-title"),
                                        html.Div(id="renewal-buckets"),
                                    ]
                                ),
                                className="panel-card",
                            ),
                        ],
                        lg=4,
                    ),
                ],
                className="g-4",
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(id="subscription-modal-title")),
                    dbc.ModalBody(
                        [
                            dbc.Alert(id="subscription-form-alert", is_open=False, color="danger"),
                            dbc.Input(id="subscription-id", type="hidden"),
                            dbc.Label("Subscription Name", className="form-label"),
                            dbc.Input(id="subscription-name", type="text", placeholder="Netflix"),
                            dbc.Label("Category", className="form-label mt-3"),
                            dbc.Select(
                                id="subscription-category",
                                options=_category_options(),
                            ),
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
                                value=date.today().isoformat(),
                            ),
                            dbc.Label("Notes", className="form-label mt-3"),
                            dbc.Textarea(
                                id="subscription-notes",
                                placeholder="Optional notes, reminders, plan details",
                                style={"minHeight": "110px"},
                            ),
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
            message = f"{name} updated successfully."
        else:
            create_subscription(
                user.id,
                name,
                int(category_id),
                float(cost),
                billing_cycle,
                renewal_date,
                notes,
            )
            message = f"{name} added successfully."
        rows = _serialize(fetch_subscriptions(user.id))
        return rows, message, True, False, "", False

    if not subscription_id:
        return no_update, "", False, False, "", False

    deleted = delete_subscription(user.id, int(subscription_id))
    if not deleted:
        return no_update, "", False, False, "", False

    rows = _serialize(fetch_subscriptions(user.id))
    return rows, "Subscription deleted.", True, False, "", False


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
def update_subscription_view(rows, search_value, category_value, sort_value, selected_rows):
    filtered_rows = _filter_rows(rows or [], search_value, category_value, sort_value)
    selected = None
    if filtered_rows and selected_rows:
        selected_index = selected_rows[0]
        if 0 <= selected_index < len(filtered_rows):
            selected = filtered_rows[selected_index]

    if selected is None:
        detail = html.Div("Select a subscription to inspect and manage it.", className="empty-state")
        selected_id = None
    else:
        detail = html.Div(
            [
                html.H4(selected["name"], className="detail-title"),
                html.Div(selected["category"], className="detail-category"),
                html.Div(f"${selected['cost']:,.2f} · {selected['billing_cycle']}", className="detail-price"),
                html.Div(
                    datetime.strptime(selected["renewal_date"], "%Y-%m-%d").strftime("%b %d, %Y"),
                    className="detail-date",
                ),
                html.P(selected["notes"] or "No notes added.", className="detail-notes"),
            ]
        )
        selected_id = selected["id"]

    today_items = [row for row in rows or [] if row["days_until"] <= 0]
    week_items = [row for row in rows or [] if 0 < row["days_until"] <= 7]
    month_items = [row for row in rows or [] if 7 < row["days_until"] <= 30]
    bucket_cards = []
    for label, items in [
        ("Renewing Today", today_items),
        ("Renewing This Week", week_items),
        ("Renewing This Month", month_items),
    ]:
        names = ", ".join(item["name"] for item in items[:3]) if items else "No subscriptions in this bucket."
        bucket_cards.append(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Div(label, className="bucket-title"),
                        html.Div(str(len(items)), className="bucket-count"),
                        html.Div(names, className="bucket-copy"),
                    ]
                ),
                className="bucket-card",
            )
        )

    return filtered_rows, detail, bucket_cards, selected_id


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
    if triggered == "close-subscription-modal":
        return False, no_update, None, "", _category_options()[0]["value"], None, "Monthly", date.today().isoformat(), "", "", False

    if triggered == "open-subscription-modal":
        default_category = _category_options()[0]["value"] if _category_options() else None
        return (
            True,
            "Add Subscription",
            None,
            "",
            default_category,
            None,
            "Monthly",
            date.today().isoformat(),
            "",
            "",
            False,
        )

    if not subscription_id:
        return True, "Edit Subscription", None, "", _category_options()[0]["value"], None, "Monthly", date.today().isoformat(), "", "Select a subscription before editing.", True

    user = current_user()
    if user is None:
        return True, "Edit Subscription", None, "", _category_options()[0]["value"], None, "Monthly", date.today().isoformat(), "", "Session expired. Sign in again.", True

    subscription = fetch_subscription(int(subscription_id), user.id)
    if subscription is None:
        return True, "Edit Subscription", None, "", _category_options()[0]["value"], None, "Monthly", date.today().isoformat(), "", "Subscription not found.", True

    return (
        True,
        "Edit Subscription",
        subscription.id,
        subscription.name,
        subscription.category_id,
        subscription.cost,
        subscription.billing_cycle,
        subscription.renewal_date.isoformat(),
        subscription.notes or "",
        "",
        False,
    )
