"""
Gmail OAuth 2.0 integration for SubTrack.

Requires three environment variables:
    GOOGLE_CLIENT_ID      — OAuth client ID from Google Cloud Console
    GOOGLE_CLIENT_SECRET  — OAuth client secret
    GOOGLE_REDIRECT_URI   — Defaults to http://localhost:8050/auth/google/callback

Setup (one-time):
1. Create a project at https://console.cloud.google.com
2. Enable the Gmail API under "APIs & Services > Library"
3. Create an OAuth 2.0 client ID (Web application type) under "APIs & Services > Credentials"
4. Add http://localhost:8050/auth/google/callback as an Authorized redirect URI
5. Copy the client ID and secret into the env vars above
"""
from __future__ import annotations

import os
import re
from datetime import datetime

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# Redirect URI for Gmail scanner (requires existing login)
REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8050/auth/google/callback"
)
# Redirect URI for Sign in with Google (no existing login required)
SIGNIN_REDIRECT_URI = os.environ.get(
    "GOOGLE_SIGNIN_REDIRECT_URI", "http://localhost:8050/auth/google/signin/callback"
)

# Allow OAuth token exchange over http:// (localhost only — never set this in production)
if REDIRECT_URI.startswith("http://") or SIGNIN_REDIRECT_URI.startswith("http://"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SIGNIN_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def is_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def _make_flow():
    from google_auth_oauthlib.flow import Flow  # lazy import — optional dependency

    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def get_auth_url() -> tuple[str, str, str | None]:
    """Return (authorization_url, state, code_verifier) for the Google consent screen."""
    flow = _make_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account consent",
    )
    code_verifier = flow.code_verifier
    return auth_url, state, code_verifier


def exchange_code(code: str, code_verifier: str | None = None) -> dict:
    """Exchange an authorization code for tokens. Returns a dict with token data."""
    flow = _make_flow()
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry,
    }


# ---------------------------------------------------------------------------
# Sign in with Google
# ---------------------------------------------------------------------------

def _make_signin_flow():
    from google_auth_oauthlib.flow import Flow

    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [SIGNIN_REDIRECT_URI],
            }
        },
        scopes=SIGNIN_SCOPES,
        redirect_uri=SIGNIN_REDIRECT_URI,
    )


def get_signin_url() -> tuple[str, str, str | None]:
    """Return (authorization_url, state, code_verifier) for Google Sign-In."""
    flow = _make_signin_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="select_account",
    )
    code_verifier = flow.code_verifier
    return auth_url, state, code_verifier


def exchange_signin_code(code: str, code_verifier: str | None = None) -> dict:
    """
    Exchange a sign-in authorization code.
    Returns {google_sub, email, name} from Google's userinfo endpoint.
    """
    import requests as rqs

    flow = _make_signin_flow()
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials

    resp = rqs.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=10,
    )
    resp.raise_for_status()
    info = resp.json()
    return {
        "google_sub": info.get("id", ""),
        "email": info.get("email", ""),
        "name": info.get("name", ""),
    }


# ---------------------------------------------------------------------------
# Subscription detection patterns
# ---------------------------------------------------------------------------

_SERVICE_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"netflix", re.I), "Netflix", "Streaming"),
    (re.compile(r"spotify", re.I), "Spotify", "Music"),
    (re.compile(r"openai|chatgpt", re.I), "ChatGPT", "Productivity"),
    (re.compile(r"google\s?one|google\s+storage|google\s+drive", re.I), "Google One", "Cloud Storage"),
    (re.compile(r"amazon\s+prime|prime\s+video|prime\s+membership", re.I), "Prime Video", "Streaming"),
    (re.compile(r"apple\s+tv", re.I), "Apple TV+", "Streaming"),
    (re.compile(r"apple\s+music", re.I), "Apple Music", "Music"),
    (re.compile(r"apple\s+one", re.I), "Apple One", "Streaming"),
    (re.compile(r"icloud", re.I), "iCloud+", "Cloud Storage"),
    (re.compile(r"microsoft\s+365|office\s+365|m365", re.I), "Microsoft 365", "Productivity"),
    (re.compile(r"youtube\s+premium", re.I), "YouTube Premium", "Streaming"),
    (re.compile(r"disney\s*\+|disney\s+plus|hotstar", re.I), "Disney+/Hotstar", "Streaming"),
    (re.compile(r"hbo\s*max|\bmax\b.*subscription", re.I), "Max (HBO)", "Streaming"),
    (re.compile(r"paramount\s*\+", re.I), "Paramount+", "Streaming"),
    (re.compile(r"\bhulu\b", re.I), "Hulu", "Streaming"),
    (re.compile(r"crunchyroll", re.I), "Crunchyroll", "Streaming"),
    (re.compile(r"twitch\s+prime|twitch\s+turbo", re.I), "Twitch", "Streaming"),
    (re.compile(r"peacock", re.I), "Peacock", "Streaming"),
    (re.compile(r"dropbox", re.I), "Dropbox", "Cloud Storage"),
    (re.compile(r"\bnotion\b", re.I), "Notion", "Productivity"),
    (re.compile(r"\bgithub\b", re.I), "GitHub", "Productivity"),
    (re.compile(r"adobe", re.I), "Adobe Creative Cloud", "Productivity"),
    (re.compile(r"\bslack\b", re.I), "Slack", "Productivity"),
    (re.compile(r"\bzoom\b", re.I), "Zoom", "Productivity"),
    (re.compile(r"\bcanva\b", re.I), "Canva Pro", "Productivity"),
    (re.compile(r"\bfigma\b", re.I), "Figma", "Productivity"),
    (re.compile(r"grammarly", re.I), "Grammarly", "Productivity"),
    (re.compile(r"1password", re.I), "1Password", "Productivity"),
    (re.compile(r"lastpass", re.I), "LastPass", "Productivity"),
    (re.compile(r"duolingo", re.I), "Duolingo Plus", "Productivity"),
    (re.compile(r"digitalocean", re.I), "DigitalOcean", "Hosting"),
    (re.compile(r"hostinger", re.I), "Hostinger", "Hosting"),
    (re.compile(r"namecheap", re.I), "Namecheap", "Domains"),
    (re.compile(r"godaddy", re.I), "GoDaddy", "Domains"),
    (re.compile(r"aws|amazon web services", re.I), "AWS", "Hosting"),
    (re.compile(r"\bheroku\b", re.I), "Heroku", "Hosting"),
    (re.compile(r"nordvpn|expressvpn|surfshark", re.I), "VPN Service", "Productivity"),
    (re.compile(r"patreon", re.I), "Patreon", "Streaming"),
]

_AMOUNT_RE = re.compile(r"[\$₹€£]\s*(\d[\d,]*(?:\.\d{1,2})?)")
_YEARLY_RE = re.compile(r"\b(annual|annually|yearly|per\s+year|\/yr)\b", re.I)


def _identify_service(sender: str, subject: str) -> tuple[str, str] | None:
    text = f"{sender} {subject}"
    for pattern, name, category in _SERVICE_PATTERNS:
        if pattern.search(text):
            return name, category
    return None


def _extract_amount(text: str) -> float | None:
    m = _AMOUNT_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _billing_cycle(text: str) -> str:
    return "Yearly" if _YEARLY_RE.search(text) else "Monthly"


# ---------------------------------------------------------------------------
# Inbox scan
# ---------------------------------------------------------------------------

def scan_inbox(user_id: int) -> list[dict]:
    """
    Search the user's Gmail inbox for subscription-related emails.

    Returns a deduplicated list of detected subscription dicts:
        {name, category, amount, billing_cycle, subject, sender}

    Tokens are automatically refreshed if expired and saved back to the DB.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from subtrack.database.db import get_google_tokens, save_google_tokens

    token_data = get_google_tokens(user_id)
    if not token_data or not token_data.get("refresh_token"):
        return []

    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    if token_data.get("expiry"):
        creds.expiry = token_data["expiry"]

    if not creds.valid:
        creds.refresh(Request())
        save_google_tokens(
            user_id,
            creds.token,
            creds.refresh_token or token_data["refresh_token"],
            creds.expiry,
        )

    svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

    query = (
        "subject:(receipt OR invoice OR subscription OR renewal OR "
        '"payment confirmation" OR "order confirmation") newer_than:365d'
    )
    try:
        result = (
            svc.users().messages().list(userId="me", q=query, maxResults=150).execute()
        )
    except Exception:
        return []

    detected: dict[str, dict] = {}  # service_name → best-match entry

    for ref in result.get("messages", []):
        try:
            msg = (
                svc.users()
                .messages()
                .get(
                    userId="me",
                    id=ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )
        except Exception:
            continue

        headers = {
            h["name"]: h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }
        sender = headers.get("From", "")
        subject = headers.get("Subject", "")

        identified = _identify_service(sender, subject)
        if not identified:
            continue

        name, category = identified
        amount = _extract_amount(subject) or _extract_amount(sender)
        cycle = _billing_cycle(subject)

        # Prefer the entry that has an explicit amount over one that doesn't.
        if name not in detected or (amount and not detected[name].get("amount")):
            detected[name] = {
                "name": name,
                "category": category,
                "amount": amount,
                "billing_cycle": cycle,
                "subject": subject,
                "sender": sender,
            }

    return list(detected.values())
