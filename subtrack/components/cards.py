from dash import html

# ── Service brand color map ──────────────────────────────────────────────────
_BRAND_COLORS: dict[str, str] = {
    "netflix": "#e50914", "spotify": "#1db954", "apple music": "#fc3c44",
    "apple tv": "#1c1c1e", "apple": "#555555", "amazon prime": "#00a8e0",
    "prime video": "#00a8e0", "amazon": "#ff9900", "google one": "#4285f4",
    "google": "#4285f4", "discord": "#5865f2", "github": "#24292f",
    "slack": "#4a154b", "adobe": "#fa0f00", "microsoft": "#00a4ef",
    "notion": "#37352f", "figma": "#f24e1e", "openai": "#10a37f",
    "chatgpt": "#10a37f", "digitalocean": "#0080ff", "aws": "#ff9900",
    "heroku": "#6762a6", "hulu": "#1ce783", "disney": "#113ccf",
    "youtube": "#ff0000", "twitch": "#9146ff", "dropbox": "#0061ff",
    "icloud": "#3693f4", "canva": "#00c4cc", "zoom": "#2d8cff",
    "linear": "#5e6ad2", "vercel": "#000000", "namecheap": "#de5230",
    "cloudflare": "#f38020", "1password": "#1a8cff", "lastpass": "#d32d27",
    "nord": "#4687c7", "nordvpn": "#4687c7", "expressvpn": "#da3940",
    "grammarly": "#15c39a", "evernote": "#14cc45", "trello": "#0052cc",
    "jira": "#0052cc", "confluence": "#0052cc", "asana": "#f06a6a",
    "monday": "#f6c000", "airtable": "#18bfff", "hubspot": "#ff7a59",
    "salesforce": "#00a1e0", "shopify": "#96bf48", "stripe": "#635bff",
    "paypal": "#003087", "cultfit": "#ff3c6e", "cult": "#ff3c6e",
    "gym": "#ff3c6e", "fitness": "#ff3c6e", "hostinger": "#673de6",
    "godaddy": "#1bdbdb", "bluehost": "#1a73e8",
}

_FALLBACK_PALETTE = [
    "#6366f1", "#8b5cf6", "#ec4899", "#ef4444",
    "#f59e0b", "#10b981", "#3b82f6", "#06b6d4",
    "#f97316", "#a855f7", "#14b8a6", "#84cc16",
]


def service_color(name: str) -> str:
    lower = name.lower()
    for key, color in _BRAND_COLORS.items():
        if key in lower:
            return color
    return _FALLBACK_PALETTE[hash(lower) % len(_FALLBACK_PALETTE)]


def service_initial(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper() if len(name) >= 2 else (name[0].upper() if name else "?")


def service_avatar(name: str, size: int = 38, radius: int = 10) -> html.Div:
    return html.Div(
        service_initial(name),
        style={
            "width": f"{size}px",
            "height": f"{size}px",
            "minWidth": f"{size}px",
            "borderRadius": f"{radius}px",
            "background": service_color(name),
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "fontFamily": "'Space Grotesk', sans-serif",
            "fontSize": f"{max(10, int(size * 0.37))}px",
            "fontWeight": "700",
            "color": "#fff",
            "userSelect": "none",
            "flexShrink": "0",
        },
    )


def metric_card(title: str, value: str, helper: str, accent_class: str, icon: str = "") -> html.Div:
    return html.Div(
        [
            html.Div(
                html.I(className=f"bi {icon}"),
                className="metric-icon-wrap",
            ) if icon else None,
            html.Div(title, className="metric-label"),
            html.Div(value, className="metric-value"),
            html.P(helper, className="metric-helper"),
        ],
        className=f"metric-card {accent_class}",
    )


def renewal_status_badge(days_until: int) -> html.Span:
    if days_until <= 0:
        cls, label = "urgency-badge urgency-today", "Today"
    elif days_until <= 3:
        cls, label = "urgency-badge urgency-today", f"{days_until}d"
    elif days_until <= 7:
        cls, label = "urgency-badge urgency-soon", f"{days_until}d"
    elif days_until <= 30:
        cls, label = "urgency-badge urgency-upcoming", f"{days_until}d"
    else:
        cls, label = "urgency-badge urgency-ok", f"{days_until}d"
    return html.Span(label, className=cls)