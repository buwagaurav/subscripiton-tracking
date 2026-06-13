from __future__ import annotations

import dash
from dash import Input, Output, State, callback, clientside_callback, ctx, dcc, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from subtrack.auth import current_user


dash.register_page(__name__, path="/ai-chat", name="SubTrack AI")

_SUGGESTIONS = [
    "What am I spending monthly?",
    "What renews this week?",
    "Which is my most expensive subscription?",
    "Show all my subscriptions",
]


def layout() -> dbc.Container:
    return dbc.Container(
        [
            dcc.Store(id="chat-history", storage_type="session", data=[]),
            # Holds the user's latest message while AI is responding; None when idle
            dcc.Store(id="chat-pending", storage_type="memory", data=None),
            html.Div(id="chat-scroll-target", style={"display": "none"}),

            # ── Page header ───────────────────────────────────────────
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Beta", className="page-kicker"),
                            html.H1("SubTrack AI", className="page-title"),
                            html.P(
                                "Ask anything about your subscriptions.",
                                className="page-copy",
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-trash me-1"), "Clear"],
                        id="chat-clear-btn",
                        color="secondary",
                        size="sm",
                        className="align-self-start mt-1",
                        n_clicks=0,
                    ),
                ],
                className="page-header d-flex align-items-start gap-3",
            ),

            # ── Chat panel ────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                # Message area (no Loading wrapper — typing indicator handles it)
                                html.Div(
                                    id="chat-messages",
                                    className="chat-message-area",
                                ),

                                html.Hr(className="my-2"),

                                # Suggestion chips
                                html.Div(
                                    [
                                        html.Button(
                                            q,
                                            id={"type": "chat-chip", "index": i},
                                            className="chat-chip",
                                            n_clicks=0,
                                        )
                                        for i, q in enumerate(_SUGGESTIONS)
                                    ],
                                    className="chat-chips",
                                ),

                                # Input bar
                                dbc.InputGroup(
                                    [
                                        dbc.Input(
                                            id="chat-input",
                                            placeholder="Ask about your subscriptions...",
                                            type="text",
                                            className="chat-input",
                                            n_submit=0,
                                            autocomplete="off",
                                            disabled=False,
                                        ),
                                        dbc.Button(
                                            html.I(className="bi bi-send-fill"),
                                            id="chat-send-btn",
                                            color="primary",
                                            n_clicks=0,
                                            disabled=False,
                                        ),
                                    ],
                                    className="mt-2",
                                ),
                            ],
                            className="chat-card-body",
                        ),
                        className="panel-card chat-panel",
                    ),
                    lg={"size": 9, "offset": 0},
                    xl={"size": 8, "offset": 0},
                ),
                className="g-3",
            ),
        ],
        fluid=True,
        className="page-shell",
    )


# ── Auto-scroll to bottom ─────────────────────────────────────────────────────
clientside_callback(
    """
    function(h, p) {
        var el = document.getElementById('chat-messages');
        if (el) { setTimeout(function() { el.scrollTop = el.scrollHeight; }, 60); }
        return '';
    }
    """,
    Output("chat-scroll-target", "children"),
    Input("chat-history", "data"),
    Input("chat-pending", "data"),
    prevent_initial_call=False,
)


# ── Step 1: Append user message instantly, set pending ───────────────────────
@callback(
    Output("chat-history", "data"),
    Output("chat-pending", "data"),
    Output("chat-input", "value"),
    Output("chat-input", "disabled"),
    Output("chat-send-btn", "disabled"),
    Input("chat-send-btn", "n_clicks"),
    Input("chat-input", "n_submit"),
    State("chat-input", "value"),
    State("chat-history", "data"),
    State("chat-pending", "data"),
    prevent_initial_call=True,
)
def handle_send(_, __, message, history, pending):
    # Ignore if already waiting for AI or message is empty
    if pending or not message or not message.strip():
        raise PreventUpdate
    if current_user() is None:
        raise PreventUpdate

    msg = message.strip()
    updated = (history or []) + [{"role": "user", "content": msg}]
    return updated, msg, "", True, True  # disable input while AI responds


# ── Step 2: Call AI when pending is set, then re-enable input ────────────────
@callback(
    Output("chat-history", "data", allow_duplicate=True),
    Output("chat-pending", "data", allow_duplicate=True),
    Output("chat-input", "disabled", allow_duplicate=True),
    Output("chat-send-btn", "disabled", allow_duplicate=True),
    Input("chat-pending", "data"),
    State("chat-history", "data"),
    prevent_initial_call=True,
)
def handle_ai_response(pending, history):
    if not pending:
        raise PreventUpdate
    user = current_user()
    if user is None:
        return history, None, False, False

    from subtrack.ai.agent import run_chat

    # history already contains the user message as the last item
    context = (history or [])[:-1]
    try:
        reply = run_chat(user.id, context, pending)
    except Exception as exc:
        reply = f"Something went wrong: {exc}"

    updated = (history or []) + [{"role": "assistant", "content": reply}]
    return updated, None, False, False  # clear pending, re-enable input


# ── Suggestion chip: same two-step flow ──────────────────────────────────────
@callback(
    Output("chat-history", "data", allow_duplicate=True),
    Output("chat-pending", "data", allow_duplicate=True),
    Output("chat-input", "disabled", allow_duplicate=True),
    Output("chat-send-btn", "disabled", allow_duplicate=True),
    Input({"type": "chat-chip", "index": dash.ALL}, "n_clicks"),
    State("chat-history", "data"),
    State("chat-pending", "data"),
    prevent_initial_call=True,
)
def handle_chip(n_clicks_list, history, pending):
    if not any(n_clicks_list) or pending:
        raise PreventUpdate
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        raise PreventUpdate
    if current_user() is None:
        raise PreventUpdate

    msg = _SUGGESTIONS[triggered["index"]]
    updated = (history or []) + [{"role": "user", "content": msg}]
    return updated, msg, True, True


# ── Clear chat ────────────────────────────────────────────────────────────────
@callback(
    Output("chat-history", "data", allow_duplicate=True),
    Output("chat-pending", "data", allow_duplicate=True),
    Output("chat-input", "disabled", allow_duplicate=True),
    Output("chat-send-btn", "disabled", allow_duplicate=True),
    Input("chat-clear-btn", "n_clicks"),
    prevent_initial_call=True,
)
def clear_chat(_):
    return [], None, False, False


# ── Render messages + typing indicator ───────────────────────────────────────
@callback(
    Output("chat-messages", "children"),
    Input("chat-history", "data"),
    Input("chat-pending", "data"),
)
def render_messages(history, pending):
    if not history and not pending:
        return html.Div(
            [
                html.Div("✦", className="chat-empty-icon"),
                html.Div("SubTrack AI", className="chat-empty-title"),
                html.P(
                    "Ask me about your spending, upcoming renewals, or any specific subscription.",
                    className="chat-empty-sub",
                ),
            ],
            className="chat-empty",
        )

    bubbles = []
    for msg in (history or []):
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "user":
            bubbles.append(
                html.Div(
                    html.Div(content, className="chat-bubble chat-bubble-user"),
                    className="chat-row chat-row-user",
                )
            )
        else:
            bubbles.append(
                html.Div(
                    [
                        html.Div("AI", className="chat-ai-avatar"),
                        # Wrap Markdown in a plain div so the bubble class
                        # behaves as a normal block flex-item (fixes full-width stretch)
                        html.Div(
                            dcc.Markdown(content, dangerously_allow_html=False),
                            className="chat-bubble chat-bubble-ai",
                        ),
                    ],
                    className="chat-row chat-row-ai",
                )
            )

    # Typing indicator while AI is working
    if pending:
        bubbles.append(
            html.Div(
                [
                    html.Div("AI", className="chat-ai-avatar"),
                    html.Div(
                        [
                            html.Span(className="chat-dot"),
                            html.Span(className="chat-dot"),
                            html.Span(className="chat-dot"),
                        ],
                        className="chat-bubble chat-bubble-ai chat-typing",
                    ),
                ],
                className="chat-row chat-row-ai",
            )
        )

    return bubbles