from __future__ import annotations

from datetime import date, datetime, timedelta

import dash
from dash import ALL, Input, Output, State, callback, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from subtrack.auth import current_user
from subtrack.components.cards import (
    renewal_status_badge,
    service_avatar,
    service_color,
    service_initial,
)
from subtrack.database.db import (
    create_subscription,
    delete_subscription,
    fetch_categories,
    fetch_subscription,
    fetch_subscriptions,
    update_subscription,
)


dash.register_page(__name__, path="/subscriptions", name="Subscriptions")

_TODAY = date.today()


def _category_options() -> list[dict]:
    return [{"label": c.name, "value": c.id} for c in fetch_categories()]


def _serialize(subscriptions) -> list[dict]:
    today = date.today()
    rows = []
    for item in subscriptions:
        rows.append(
            {
                "id":           item.id,
                "name":         item.name,
                "category":     item.category.name,
                "category_id":  item.category_id,
                "cost":         round(item.cost, 2),
                "billing_cycle": item.billing_cycle,
                "renewal_date": item.renewal_date.isoformat(),
                "days_until":   (item.renewal_date - today).days,
            }
        )
    return rows


def _filter_rows(rows, search, category, sort):
    filtered = rows
    if search:
        q = search.lower()
        filtered = [r for r in filtered if q in r["name"].lower() or q in r["category"].lower()]
    if category:
        filtered = [r for r in filtered if r["category_id"] == category]
    sort_map = {
        "renewal_asc":  (lambda r: r["renewal_date"], False),
        "renewal_desc": (lambda r: r["renewal_date"], True),
        "cost_asc":     (lambda r: r["cost"], False),
        "cost_desc":    (lambda r: r["cost"], True),
    }
    if sort in sort_map:
        key_fn, reverse = sort_map[sort]
        filtered = sorted(filtered, key=key_fn, reverse=reverse)
    return filtered


def _urgency_class(days: int) -> str:
    if days <= 0:    return "urgency-today"
    if days <= 3:    return "urgency-today"
    if days <= 7:    return "urgency-soon"
    if days <= 30:   return "urgency-upcoming"
    return "urgency-ok"


def layout() -> dbc.Container:
    user = current_user()
    rows = _serialize(fetch_subscriptions(user.id)) if user else []
    today = date.today()

    return dbc.Container(
        [
            dcc.Store(id="subscriptions-store", data=rows),
            dcc.Store(id="sub-selected-id", data=None),
            dcc.Store(id="edit-trigger", data=None),

            # ── Hidden id for modal (kept for save callback) ──────────
            dbc.Input(id="subscription-id", type="hidden"),

            # ── Page header ───────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div("Manage", className="page-kicker"),
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
                            [html.I(className="bi bi-plus-lg me-1"), "Add Subscription"],
                            id="open-subscription-modal",
                            color="primary",
                            className="action-button",
                        ),
                        md=5,
                        className="d-flex justify-content-md-end align-items-center",
                    ),
                ],
                className="page-header g-3",
            ),

            # ── Renewal urgency buckets ───────────────────────────────
            html.Div(id="renewal-buckets", className="mb-4"),

            # ── Filter bar ───────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Input(
                            id="subscription-search",
                            placeholder="Search subscriptions…",
                            type="search",
                            className="filter-input",
                        ),
                        xs=12, md=5,
                    ),
                    dbc.Col(
                        dbc.Select(
                            id="subscription-category-filter",
                            options=[{"label": "All categories", "value": ""}]
                            + _category_options(),
                            value="",
                            className="filter-select",
                        ),
                        xs=6, md=3,
                    ),
                    dbc.Col(
                        dbc.Select(
                            id="subscription-sort",
                            options=[
                                {"label": "Renews soonest",  "value": "renewal_asc"},
                                {"label": "Renews latest",   "value": "renewal_desc"},
                                {"label": "Cost: low → high", "value": "cost_asc"},
                                {"label": "Cost: high → low", "value": "cost_desc"},
                            ],
                            value="renewal_asc",
                            className="filter-select",
                        ),
                        xs=6, md=4,
                    ),
                ],
                className="g-2 mb-4",
            ),

            # ── Cards grid + detail panel ─────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(id="subscription-cards-container"),
                        lg=8,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div("Selected item", className="section-kicker"),
                                    html.H3("Details", className="section-title"),
                                    html.Div(id="subscription-detail-panel"),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Button(
                                                    [html.I(className="bi bi-pencil me-1"), "Edit"],
                                                    id="edit-subscription-button",
                                                    color="secondary",
                                                    className="w-100",
                                                )
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    [html.I(className="bi bi-trash me-1"), "Delete"],
                                                    id="delete-subscription-button",
                                                    color="danger",
                                                    className="w-100",
                                                )
                                            ),
                                        ],
                                        className="g-2 mt-3",
                                        id="detail-action-row",
                                        style={"display": "none"},
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

            # ── Add / Edit modal ──────────────────────────────────────
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(id="subscription-modal-title")),
                    dbc.ModalBody(
                        [
                            dbc.Alert(id="subscription-form-alert", is_open=False, color="danger"),
                            dbc.Label("Subscription Name", className="form-label"),
                            dbc.Input(id="subscription-name", type="text",
                                      placeholder="e.g. Netflix"),
                            dbc.Label("Category", className="form-label mt-3"),
                            dbc.Select(id="subscription-category",
                                       options=_category_options()),
                            dbc.Label("Cost", className="form-label mt-3"),
                            dbc.Input(id="subscription-cost", type="number",
                                      min=0, step=0.01, placeholder="0.00"),
                            dbc.Label("Billing Cycle", className="form-label mt-3"),
                            dbc.Select(
                                id="subscription-billing-cycle",
                                options=[
                                    {"label": "Monthly", "value": "Monthly"},
                                    {"label": "Yearly",  "value": "Yearly"},
                                ],
                                value="Monthly",
                            ),
                            dbc.Label("Renewal Date", className="form-label mt-3"),
                            dbc.Input(
                                id="subscription-renewal-date",
                                type="date",
                                value=_TODAY.isoformat(),
                            ),
                            dbc.Label("Notes (optional)", className="form-label mt-3"),
                            dbc.Textarea(id="subscription-notes",
                                         placeholder="Any notes…", rows=2),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button("Cancel", id="close-subscription-modal",
                                       color="secondary", outline=False),
                            dbc.Button(
                                [html.I(className="bi bi-check-lg me-1"), "Save"],
                                id="save-subscription-button", color="primary",
                            ),
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
                header="Done",
                is_open=False,
                dismissable=True,
                duration=3500,
                icon="success",
                className="toast-shell",
            ),
        ],
        fluid=True,
        className="page-shell",
    )


# ── Card renderer ────────────────────────────────────────────────────────────

def _render_sub_card(row: dict, is_selected: bool) -> html.Div:
    days  = row["days_until"]
    color = service_color(row["name"])
    init  = service_initial(row["name"])
    badge = html.Span(
        "Today" if days <= 0 else f"{days}d",
        className=f"urgency-badge {_urgency_class(days)}",
    )
    return html.Div(
        [
            # clickable top section
            html.Div(
                [
                    html.Div(init, className="sub-service-avatar",
                             style={"background": color}),
                    html.Div(
                        [
                            html.Div(row["name"],     className="sub-name"),
                            html.Div(row["category"], className="sub-category"),
                        ],
                        style={"flex": "1", "minWidth": "0"},
                    ),
                    badge,
                ],
                className="sub-card-top",
                id={"type": "sub-card-click", "index": row["id"]},
                n_clicks=0,
            ),
            # cost
            html.Div(
                [
                    html.Span(f"${row['cost']:,.2f}", className="sub-cost"),
                    html.Span(f"/ {row['billing_cycle'].lower()}", className="sub-cycle"),
                ],
                className="sub-cost-row",
            ),
            html.Div(
                "Renews "
                + datetime.strptime(row["renewal_date"], "%Y-%m-%d").strftime("%b %d, %Y"),
                className="sub-renewal",
            ),
            # footer actions
            html.Div(
                [
                    html.Span(style={"flex": "1"}),
                    html.Div(
                        [
                            html.Button(
                                html.I(className="bi bi-pencil"),
                                id={"type": "edit-card", "index": row["id"]},
                                n_clicks=0,
                                className="sub-action-btn",
                                title="Edit",
                            ),
                            html.Button(
                                html.I(className="bi bi-trash"),
                                id={"type": "delete-card", "index": row["id"]},
                                n_clicks=0,
                                className="sub-action-btn delete",
                                title="Delete",
                            ),
                        ],
                        className="sub-actions",
                    ),
                ],
                className="sub-card-footer",
            ),
        ],
        className="sub-card" + (" sub-card-selected" if is_selected else ""),
    )


# ── Save / Delete (modal form) ───────────────────────────────────────────────

@callback(
    Output("subscriptions-store",       "data"),
    Output("subscription-toast",        "children"),
    Output("subscription-toast",        "is_open"),
    Output("subscription-modal",        "is_open",   allow_duplicate=True),
    Output("subscription-form-alert",   "children"),
    Output("subscription-form-alert",   "is_open"),
    Input("save-subscription-button",   "n_clicks"),
    State("subscription-id",            "value"),
    State("subscription-name",          "value"),
    State("subscription-category",      "value"),
    State("subscription-cost",          "value"),
    State("subscription-billing-cycle", "value"),
    State("subscription-renewal-date",  "value"),
    State("subscription-notes",         "value"),
    prevent_initial_call=True,
)
def save_subscription(
    _save_clicks,
    subscription_id, name, category_id, cost, billing_cycle, renewal_date_value, notes,
):
    user = current_user()
    if user is None:
        return no_update, "", False, False, "Session expired. Sign in again.", True

    if not all([name, category_id, cost, billing_cycle, renewal_date_value]):
        return no_update, "", False, True, "All required fields must be filled in.", True

    renewal_date = datetime.strptime(renewal_date_value, "%Y-%m-%d").date()

    if subscription_id:
        updated = update_subscription(
            user.id, int(subscription_id), name, int(category_id),
            float(cost), billing_cycle, renewal_date, notes,
        )
        if not updated:
            return no_update, "", False, True, "Subscription no longer exists.", True
        message = f"{name} updated."
    else:
        create_subscription(
            user.id, name, int(category_id), float(cost), billing_cycle, renewal_date, notes,
        )
        message = f"{name} added."

    return _serialize(fetch_subscriptions(user.id)), message, True, False, "", False


# ── Delete from card ─────────────────────────────────────────────────────────

@callback(
    Output("subscriptions-store", "data",     allow_duplicate=True),
    Output("subscription-toast",  "children", allow_duplicate=True),
    Output("subscription-toast",  "is_open",  allow_duplicate=True),
    Input({"type": "delete-card", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def delete_from_card(n_clicks_list):
    triggered = dash.ctx.triggered_id
    if not isinstance(triggered, dict):
        raise PreventUpdate
    if not any(n for n in n_clicks_list if n):
        raise PreventUpdate
    user = current_user()
    if user is None:
        raise PreventUpdate
    sub_id = triggered["index"]
    if delete_subscription(user.id, int(sub_id)):
        return _serialize(fetch_subscriptions(user.id)), "Subscription deleted.", True
    raise PreventUpdate


# ── Delete from detail panel ─────────────────────────────────────────────────

@callback(
    Output("subscriptions-store", "data",     allow_duplicate=True),
    Output("subscription-toast",  "children", allow_duplicate=True),
    Output("subscription-toast",  "is_open",  allow_duplicate=True),
    Input("delete-subscription-button", "n_clicks"),
    State("subscription-id", "value"),
    prevent_initial_call=True,
)
def delete_from_panel(_click, subscription_id):
    if not subscription_id:
        raise PreventUpdate
    user = current_user()
    if user is None:
        raise PreventUpdate
    if delete_subscription(user.id, int(subscription_id)):
        return _serialize(fetch_subscriptions(user.id)), "Subscription deleted.", True
    raise PreventUpdate


# ── Card click → set selected ────────────────────────────────────────────────

@callback(
    Output("sub-selected-id", "data"),
    Input({"type": "sub-card-click", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_card(n_clicks_list):
    triggered = dash.ctx.triggered_id
    if not isinstance(triggered, dict):
        raise PreventUpdate
    if not any(n for n in n_clicks_list if n):
        raise PreventUpdate
    return triggered["index"]


# ── Edit card btn → capture trigger ─────────────────────────────────────────

@callback(
    Output("edit-trigger", "data"),
    Input({"type": "edit-card", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def capture_edit_trigger(n_clicks_list):
    triggered = dash.ctx.triggered_id
    if not isinstance(triggered, dict):
        raise PreventUpdate
    if not any(n for n in n_clicks_list if n):
        raise PreventUpdate
    return triggered["index"]


# ── Render cards + detail + buckets ──────────────────────────────────────────

@callback(
    Output("subscription-cards-container", "children"),
    Output("renewal-buckets",              "children"),
    Output("subscription-detail-panel",    "children"),
    Output("detail-action-row",            "style"),
    Output("subscription-id",              "value"),
    Input("subscriptions-store",           "data"),
    Input("subscription-search",           "value"),
    Input("subscription-category-filter",  "value"),
    Input("subscription-sort",             "value"),
    Input("sub-selected-id",               "data"),
)
def render_view(rows, search, category, sort, selected_id):
    all_rows  = rows or []
    filtered  = _filter_rows(all_rows, search, category, sort)

    # ── Cards ──────────────────────────────────────────────────────────────
    if filtered:
        card_cols = [
            dbc.Col(
                _render_sub_card(row, str(selected_id) == str(row["id"]) if selected_id else False),
                xs=12, sm=6, xl=4,
                className="mb-1",
            )
            for row in filtered
        ]
        cards_content = dbc.Row(card_cols, className="g-3")
    else:
        cards_content = html.Div(
            [
                html.Div("📋", className="empty-state-icon"),
                html.Div("No subscriptions found", className="empty-state-text"),
                html.P("Try a different search or add your first subscription.",
                       className="empty-state-sub"),
            ],
            className="empty-state",
        )

    # ── Detail panel ───────────────────────────────────────────────────────
    selected_row = next(
        (r for r in all_rows if selected_id and str(r["id"]) == str(selected_id)),
        None,
    )

    if selected_row:
        days  = selected_row["days_until"]
        color = service_color(selected_row["name"])
        init  = service_initial(selected_row["name"])
        detail = html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            init,
                            className="sub-service-avatar",
                            style={
                                "background": color,
                                "width": "50px", "height": "50px",
                                "borderRadius": "13px", "fontSize": "1rem",
                            },
                        ),
                        html.Div(
                            [
                                html.H4(selected_row["name"],     className="detail-title"),
                                html.Div(selected_row["category"], className="detail-category"),
                            ],
                            style={"marginLeft": "0.75rem"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center", "marginBottom": "1rem"},
                ),
                html.Div(
                    f"${selected_row['cost']:,.2f} · {selected_row['billing_cycle']}",
                    className="detail-price",
                ),
                html.Div(
                    [
                        html.Span(
                            datetime.strptime(
                                selected_row["renewal_date"], "%Y-%m-%d"
                            ).strftime("%b %d, %Y"),
                            className="detail-date me-2",
                        ),
                        html.Span(
                            "Today" if days <= 0 else f"{days}d",
                            className=f"urgency-badge {_urgency_class(days)}",
                        ),
                    ],
                    style={"marginTop": "0.5rem", "display": "flex", "alignItems": "center"},
                ),
            ]
        )
        action_style = {}
        selected_id_value = selected_row["id"]
    else:
        detail = html.Div(
            [
                html.Div("🔍", className="empty-state-icon"),
                html.Div("No subscription selected", className="empty-state-text"),
                html.P("Click any card to see details.", className="empty-state-sub"),
            ],
            className="empty-state",
        )
        action_style = {"display": "none"}
        selected_id_value = None

    # ── Bucket summary ─────────────────────────────────────────────────────
    buckets = [
        ("Today",      "urgency-today",    [r for r in all_rows if r["days_until"] <= 0]),
        ("This Week",  "urgency-soon",     [r for r in all_rows if 0 < r["days_until"] <= 7]),
        ("This Month", "urgency-upcoming", [r for r in all_rows if 7 < r["days_until"] <= 30]),
        ("Later",      "urgency-ok",       [r for r in all_rows if r["days_until"] > 30]),
    ]
    bucket_cols = []
    for label, _cls, items in buckets:
        names = (
            ", ".join(r["name"] for r in items[:3]) + ("…" if len(items) > 3 else "")
            if items else "—"
        )
        bucket_cols.append(
            dbc.Col(
                html.Div(
                    [
                        html.Div(label, className="bucket-label"),
                        html.Div(str(len(items)), className="bucket-count"),
                        html.Div(names, className="bucket-copy"),
                    ],
                    className="bucket-card h-100",
                ),
                xs=6, lg=3,
            )
        )

    return cards_content, dbc.Row(bucket_cols, className="g-3"), detail, action_style, selected_id_value


# ── Modal open / edit / close ─────────────────────────────────────────────────

@callback(
    Output("subscription-modal",        "is_open",   allow_duplicate=True),
    Output("subscription-modal-title",  "children"),
    Output("subscription-id",           "value",     allow_duplicate=True),
    Output("subscription-name",         "value"),
    Output("subscription-category",     "value"),
    Output("subscription-cost",         "value"),
    Output("subscription-billing-cycle","value"),
    Output("subscription-renewal-date", "value"),
    Output("subscription-notes",        "value"),
    Output("subscription-form-alert",   "children",  allow_duplicate=True),
    Output("subscription-form-alert",   "is_open",   allow_duplicate=True),
    Input("open-subscription-modal",    "n_clicks"),
    Input("edit-trigger",               "data"),
    Input("edit-subscription-button",   "n_clicks"),
    Input("close-subscription-modal",   "n_clicks"),
    State("subscription-id",            "value"),
    prevent_initial_call=True,
)
def manage_modal(
    _open_clicks, edit_id, _edit_panel_click, _close_clicks, current_sub_id,
):
    triggered = dash.ctx.triggered_id
    opts = _category_options()
    default_cat = opts[0]["value"] if opts else None
    blank = ("", default_cat, None, "Monthly", date.today().isoformat(), "", "", False)

    if triggered == "close-subscription-modal":
        return (False, no_update, None) + blank

    if triggered == "open-subscription-modal":
        return (True, "New Subscription", None) + blank

    # determine which sub ID to edit
    if triggered == "edit-trigger":
        if not edit_id:
            raise PreventUpdate
        target_id = edit_id
    else:
        # edit panel button — use current_sub_id from hidden input
        target_id = current_sub_id

    if not target_id:
        return (True, "Edit Subscription", None) + blank[:6] + ("Select a subscription first.", True)

    user = current_user()
    if user is None:
        return (True, "Edit Subscription", None) + blank[:6] + ("Session expired.", True)

    sub = fetch_subscription(int(target_id), user.id)
    if sub is None:
        return (True, "Edit Subscription", None) + blank[:6] + ("Subscription not found.", True)

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