\# SubTrack

SubTrack is a Dash-based MVP for manually tracking recurring subscriptions from one dashboard. It is designed for fast validation: simple local setup, SQLite storage, practical CRUD flows, immediate visibility into renewal risk and recurring spend, and optional Gmail scanning to auto-detect subscriptions from inbox receipts.

## Stack

- Python 3.12
- Dash 2.18.2 + Dash Bootstrap Components
- Plotly
- SQLite + SQLAlchemy 2.0
- Flask sessions (server-side auth)
- Google OAuth 2.0 + Gmail API (optional)
- Docker + Docker Compose

## Project Structure

```text
subtrack/
├── app.py                 # Dash app, Flask server, auth routes
├── auth.py                # Session-based login/logout helpers
├── gmail.py               # Gmail OAuth flow + inbox scanner
├── assets/
│   └── styles.css
├── components/
│   ├── cards.py
│   ├── navbar.py
│   └── sidebar.py
├── database/
│   ├── db.py              # CRUD, migrations, seed data, token helpers
│   └── models.py          # SQLAlchemy ORM models
├── pages/
│   ├── analytics.py
│   ├── dashboard.py
│   ├── gmail_import.py    # Gmail import page (connect, scan, add)
│   ├── login.py
│   └── subscriptions.py
└── data/
    └── subtrack.db        # Auto-created on first run
```

## Database Schema

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `full_name` | VARCHAR(120) | |
| `email` | VARCHAR(150) UNIQUE | |
| `password_hash` | VARCHAR(255) | werkzeug PBKDF2 |
| `created_at` | DATETIME | |
| `google_access_token` | TEXT | Set after Gmail connect |
| `google_refresh_token` | TEXT | Set after Gmail connect |
| `google_token_expiry` | DATETIME | Auto-refreshed on scan |

### `categories`

| Column | Type |
|---|---|
| `id` | INTEGER PK |
| `name` | VARCHAR(100) UNIQUE |

### `subscriptions`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `user_id` | INTEGER FK → users | |
| `name` | VARCHAR(150) | |
| `category_id` | INTEGER FK → categories | |
| `cost` | FLOAT | |
| `billing_cycle` | VARCHAR(20) | `Monthly` or `Yearly` |
| `renewal_date` | DATE | |
| `notes` | TEXT NULL | |
| `created_at` | DATETIME | |

## Authentication

SubTrack uses Flask session-based auth with four seeded demo users. Sessions are cookie-backed, HTTP-only, and protected by Flask's `before_request` guard on every server-side route.

**Login flow:**
1. User submits credentials on `/login`
2. Dash callback verifies against hashed password in DB
3. On success: `session["user_id"]` is set, browser redirects to `/`
4. All subsequent page navigations are either client-side (Dash React Router) or protected by `before_request`

**Logout:** clicking "Logout" in the navbar hits `/do-logout`, which clears the session and redirects to `/login`.

## Gmail OAuth Integration

SubTrack can scan your Gmail inbox for subscription receipts and renewal emails to suggest what to add to your tracker. The integration uses OAuth 2.0 with read-only Gmail access — it never sends email, reads personal messages, or modifies anything.

### How it works

```
User clicks "Connect Gmail"
        │
        ▼
GET /auth/google  ──────────────────────────────────────────────────────────────┐
        │                                                                        │
        │  Flask builds Google OAuth URL (scope: gmail.readonly, offline mode)  │
        ▼                                                                        │
Google consent screen                                                            │
        │                                                                        │
        │  User approves                                                         │
        ▼                                                                        │
GET /auth/google/callback?code=xxx&state=yyy                                     │
        │                                                                        │
        │  1. Verify CSRF state matches session                                  │
        │  2. Exchange authorization code → access_token + refresh_token        │
        │  3. Store tokens in users.google_access_token / google_refresh_token  │
        ▼                                                                        │
Redirect to /gmail-import ───────────────────────────────────────────────────────┘
        │
        ▼
User clicks "Scan Inbox"
        │
        ▼
Dash callback calls gmail.scan_inbox(user_id)
        │
        │  1. Load tokens from DB
        │  2. Refresh access token if expired, save new token
        │  3. Gmail API: search last 365 days for receipts/invoices/renewals
        │  4. For each email: check sender + subject against 35+ service patterns
        │  5. Extract amount with regex ($X.XX, ₹X, etc.)
        │  6. Deduplicate by service name (prefer entry with an amount)
        ▼
Result cards rendered in the browser
        │
        ▼
User clicks "Add to SubTrack" on any card
        │
        ▼
create_subscription() called → subscription appears in tracker
```

### Setup

**Google Cloud Console (one time):**

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a new project
2. Navigate to **APIs & Services → Library** and enable **Gmail API**
3. Navigate to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
4. Set Application type to **Web application**
5. Under **Authorized redirect URIs**, add **both** of these:
   - `http://localhost:8050/auth/google/signin/callback` ← for Sign in with Google
   - `http://localhost:8050/auth/google/callback` ← for Gmail inbox scanner
6. Copy the **Client ID** and **Client Secret**

**Environment variables:**

```bash
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"
# These are optional — the defaults match a standard local run
# export GOOGLE_REDIRECT_URI="http://localhost:8050/auth/google/callback"
# export GOOGLE_SIGNIN_REDIRECT_URI="http://localhost:8050/auth/google/signin/callback"
```

If these variables are not set, the "Sign in with Google" button is hidden on the login page, the Gmail Import page shows a setup guide, and all email/password features work normally.

### What the scanner detects

The scanner searches Gmail for emails whose subject contains `receipt`, `invoice`, `subscription`, `renewal`, or `payment confirmation` sent in the past 12 months. It then matches the sender and subject against 35+ service patterns:

Netflix, Spotify, ChatGPT/OpenAI, Google One, Prime Video, Apple TV+, Apple Music, iCloud+, Microsoft 365, YouTube Premium, Disney+/Hotstar, Dropbox, Notion, GitHub, Adobe Creative Cloud, Slack, Zoom, Canva Pro, Figma, Grammarly, 1Password, DigitalOcean, Hostinger, Namecheap, GoDaddy, AWS, and more.

## MVP Features

- **Sign in with Google** — one-click login on the login page; creates an account automatically on first use
- Login and logout flow with Flask session-based auth (email/password)
- Per-user subscription ownership and isolated dashboards
- Dashboard with monthly spend, annual spend, active count, and renewals due this week
- Renewal alerts sorted by urgency
- Subscriptions page sorted by upcoming renewal date with urgency buckets (Today / This Week / This Month / Later)
- Subscription CRUD: add, edit, delete, and detail view
- Search, category filter, and sort controls
- Analytics page: spend-by-category pie chart, monthly bar chart, renewal timeline
- **Gmail Import**: connect Gmail, scan inbox for receipts, add detected subscriptions in one click
- Dark-mode responsive layout with sidebar navigation
- SQLite auto-migration and seed data on first run
- Dockerized local run

## Local Run

### Without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: set Gmail env vars before starting
export GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET="..."

python -m subtrack.app
```

Open `http://localhost:8050`. You will land on the login screen first.

### Docker

```bash
docker-compose up --build
```

To pass Gmail credentials into Docker:

```bash
GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... docker-compose up --build
```

## Demo Login Credentials

| Name | Email | Password |
|---|---|---|
| Aarav Mehta | `aarav@subtrack.dev` | `Aarav@123` |
| Diya Kapoor | `diya@subtrack.dev` | `Diya@123` |
| Rohan Iyer | `rohan@subtrack.dev` | `Rohan@123` |
| Sara Thomas | `sara@subtrack.dev` | `Sara@123` |

## Seed Data

On first launch the app seeds categories, the four demo users, and sample subscriptions across Netflix, Prime Video, Hotstar, Spotify, ChatGPT, Google One, domains, hosting, and fitness memberships. Subsequent launches skip seeding if records exist.

SQLite data lives at `subtrack/data/subtrack.db`.

## What To Build Next

- Email and push renewal reminders (extend the Gmail OAuth scope to send)
- Calendar integration: add renewals to Google Calendar via the existing OAuth token
- Import from bank statement CSV or PDF
- Recurring spend trend analysis over time
- Budgeting goals and cancellation recommendations
- Multi-currency support

## Product-Market Fit Metrics

- Weekly active users
- Subscriptions tracked per user
- Percentage of users returning before renewal dates
- Gmail import adoption rate (connected / total users)
- Subscriptions added via Gmail vs manually
- CRUD completion rate after first session
- 7-day and 30-day retention
- Monthly active users with 3+ subscriptions tracked

## Notes

- Single-process architecture — easy to ship and operate at validation scale.
- SQLite is sufficient for the MVP and can be swapped for PostgreSQL with minimal ORM changes.
- Gmail tokens are stored in plaintext SQLite — acceptable for a local single-user instance; encrypt at rest before multi-tenant production use.
- The Gmail scanner fetches metadata only (sender, subject, date headers) — it does not read email bodies.