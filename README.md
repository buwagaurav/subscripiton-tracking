# SubTrack

SubTrack is a Dash-based MVP for manually tracking recurring subscriptions from one dashboard. It is designed for fast validation: simple local setup, SQLite storage, practical CRUD flows, and immediate visibility into renewal risk and recurring spend.

## Stack

- Python 3.11
- Dash + Dash Bootstrap Components
- Plotly
- SQLite
- SQLAlchemy
- Docker + Docker Compose

## Project Structure

```text
subtrack/
├── app.py
├── assets/
│   └── styles.css
├── components/
│   ├── cards.py
│   ├── navbar.py
│   └── sidebar.py
├── database/
│   ├── db.py
│   └── models.py
├── pages/
│   ├── analytics.py
│   ├── dashboard.py
│   ├── login.py
│   └── subscriptions.py
└── data/
```

## Database Schema

### `users`

- `id` INTEGER PRIMARY KEY
- `full_name` VARCHAR(120) NOT NULL
- `email` VARCHAR(150) UNIQUE NOT NULL
- `password_hash` VARCHAR(255) NOT NULL
- `created_at` DATETIME NOT NULL

### `categories`

- `id` INTEGER PRIMARY KEY
- `name` VARCHAR(100) UNIQUE NOT NULL

### `subscriptions`

- `id` INTEGER PRIMARY KEY
- `user_id` INTEGER NOT NULL REFERENCES `users.id`
- `name` VARCHAR(150) NOT NULL
- `category_id` INTEGER NOT NULL REFERENCES `categories.id`
- `cost` FLOAT NOT NULL
- `billing_cycle` VARCHAR(20) NOT NULL
- `renewal_date` DATE NOT NULL
- `notes` TEXT NULL
- `created_at` DATETIME NOT NULL

## MVP Features Included

- Seeded login and logout flow with authenticated onboarding
- Per-user subscription ownership and isolated dashboards
- Dashboard with monthly spend, annual spend, active subscriptions, and renewals due this week
- Dashboard alerts for upcoming renewals
- Subscription CRUD with add, edit, delete, and detail view
- Search, category filter, and sort controls for the subscription table
- Upcoming renewal buckets for today, this week, and this month
- Analytics page with pie, bar, and renewal timeline charts
- Dark-mode responsive layout with sidebar navigation
- SQLite auto-seeding with realistic starter data
- Dockerized local run via `docker-compose up`

## Local Run

### Docker

```bash
docker-compose up --build
```

Then open `http://localhost:8050`.
You will land on the login screen first.

### Without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m subtrack.app
```

Then open `http://localhost:8050/login`.

## Demo Login Credentials

- `aarav@subtrack.dev` / `Aarav@123`
- `diya@subtrack.dev` / `Diya@123`
- `rohan@subtrack.dev` / `Rohan@123`
- `sara@subtrack.dev` / `Sara@123`

## Seed Data

On first launch, the app seeds categories, 4 demo users, and sample subscriptions across Netflix, Prime Video, Hotstar, Spotify, ChatGPT, Google One, domains, hosting, and fitness memberships.

SQLite data lives at `subtrack/data/subtrack.db`.

## What To Build In V2

- Email, push, and calendar renewal reminders
- Recurring spend trend analysis over time
- Import flows from bank statements or CSV exports
- Budgeting goals and cancellation recommendations
- Multi-currency support and tax-inclusive pricing support

## Product-Market Fit Metrics

- Weekly active users
- Number of subscriptions tracked per user
- Percentage of users returning before renewal dates
- Renewal alert engagement rate
- CRUD completion rate after first session
- 7-day and 30-day retention
- Monthly active users who add 3 or more subscriptions
- User-reported savings or prevented missed renewals

## Notes

- The app uses a single-process architecture to keep the MVP easy to ship and operate.
- Notifications are intentionally in-app only for this version.
- SQLite is sufficient for validation and can later be swapped for PostgreSQL with minimal ORM changes.
