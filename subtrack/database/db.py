from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session, joinedload, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from subtrack.database.models import Base, Category, Notification, Subscription, User


BASE_DIR = Path(__file__).resolve().parents[1]

_raw_url = os.environ.get("DATABASE_URL", "")
if _raw_url:
    # Neon/Heroku may return 'postgres://' — SQLAlchemy requires 'postgresql://'
    if _raw_url.startswith("postgres://"):
        _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = _raw_url
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=2,
    )
else:
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    DATABASE_URL = f"sqlite:///{DATA_DIR / 'subtrack.db'}"
    engine = create_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

DUMMY_USERS = [
    {
        "full_name": "Aarav Mehta",
        "email": "aarav@subtrack.dev",
        "password": "Aarav@123",
        "subscriptions": [
            ("Netflix", "Streaming", 15.49, "Monthly", 3, "Family plan"),
            ("Spotify", "Music", 10.99, "Monthly", 8, "Personal premium plan"),
            ("Namecheap Domain", "Domains", 14.98, "Yearly", 2, "Primary domain renewal"),
        ],
    },
    {
        "full_name": "Diya Kapoor",
        "email": "diya@subtrack.dev",
        "password": "Diya@123",
        "subscriptions": [
            ("Prime Video", "Streaming", 139.00, "Yearly", 24, "Bundled with Prime"),
            ("Google One", "Cloud Storage", 19.99, "Yearly", 12, "200GB plan"),
            ("Cult Gym", "Fitness", 35.00, "Monthly", 5, "Monthly membership"),
        ],
    },
    {
        "full_name": "Rohan Iyer",
        "email": "rohan@subtrack.dev",
        "password": "Rohan@123",
        "subscriptions": [
            ("ChatGPT", "Productivity", 20.00, "Monthly", 1, "Work research"),
            ("DigitalOcean", "Hosting", 24.00, "Monthly", 15, "App droplet"),
            ("iCloud+", "Cloud Storage", 2.99, "Monthly", 0, "50GB storage"),
        ],
    },
    {
        "full_name": "Sara Thomas",
        "email": "sara@subtrack.dev",
        "password": "Sara@123",
        "subscriptions": [
            ("Hotstar", "Streaming", 11.99, "Monthly", 6, "Mobile + TV plan"),
            ("Canva Pro", "Productivity", 14.99, "Monthly", 9, "Design work"),
            ("Hostinger", "Hosting", 95.88, "Yearly", 21, "Client hosting account"),
        ],
    },
]


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    seed_data()


def _run_migrations() -> None:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    with engine.begin() as connection:
        if "users" not in tables:
            User.__table__.create(bind=connection, checkfirst=True)

        if "notifications" not in tables:
            Notification.__table__.create(bind=connection, checkfirst=True)

        if "subscriptions" in tables:
            sub_cols = {col["name"] for col in inspector.get_columns("subscriptions")}
            if "user_id" not in sub_cols:
                connection.execute(text("ALTER TABLE subscriptions ADD COLUMN user_id INTEGER"))

        if "users" in tables:
            user_cols = {col["name"] for col in inspector.get_columns("users")}
            for col_name, col_type in [
                ("google_sub", "VARCHAR(100)"),
                ("google_access_token", "TEXT"),
                ("google_refresh_token", "TEXT"),
                ("google_token_expiry", "DATETIME"),
            ]:
                if col_name not in user_cols:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))


def seed_data() -> None:
    with get_session() as session:
        category_names = [
            "Streaming",
            "Music",
            "Cloud Storage",
            "Productivity",
            "Domains",
            "Hosting",
            "Fitness",
        ]
        existing_categories = {
            category.name: category
            for category in session.scalars(select(Category).order_by(Category.name)).all()
        }
        for category_name in category_names:
            if category_name not in existing_categories:
                category = Category(name=category_name)
                session.add(category)
                session.flush()
                existing_categories[category_name] = category

        existing_users = {
            user.email: user for user in session.scalars(select(User).order_by(User.id)).all()
        }
        for record in DUMMY_USERS:
            if record["email"] not in existing_users:
                user = User(
                    full_name=record["full_name"],
                    email=record["email"],
                    password_hash=generate_password_hash(record["password"]),
                )
                session.add(user)
                session.flush()
                existing_users[record["email"]] = user

        default_user = next(iter(existing_users.values()), None)
        if default_user is not None:
            legacy_rows = session.scalars(
                select(Subscription).where(Subscription.user_id.is_(None))
            ).all()
            for subscription in legacy_rows:
                subscription.user_id = default_user.id

        today = date.today()
        for record in DUMMY_USERS:
            user = existing_users[record["email"]]
            existing_names = set(
                session.scalars(
                    select(Subscription.name).where(Subscription.user_id == user.id)
                ).all()
            )
            for name, category_name, cost, billing_cycle, days_offset, notes in record["subscriptions"]:
                if name in existing_names:
                    continue
                session.add(
                    Subscription(
                        user_id=user.id,
                        name=name,
                        category_id=existing_categories[category_name].id,
                        cost=cost,
                        billing_cycle=billing_cycle,
                        renewal_date=today + timedelta(days=days_offset),
                        notes=notes,
                    )
                )


def create_user(full_name: str, email: str, password: str) -> User | None:
    """Create a new account. Returns None if the email is already registered."""
    with get_session() as session:
        existing = session.scalar(select(User).where(User.email == email.strip().lower()))
        if existing is not None:
            return None
        user = User(
            full_name=full_name.strip(),
            email=email.strip().lower(),
            password_hash=generate_password_hash(password),
        )
        session.add(user)
        session.flush()
        session.refresh(user)
        return user


def fetch_categories() -> list[Category]:
    with get_session() as session:
        return session.scalars(select(Category).order_by(Category.name)).all()


def fetch_user(user_id: int) -> User | None:
    with get_session() as session:
        return session.get(User, user_id)


def fetch_demo_users() -> list[dict]:
    return [
        {
            "full_name": record["full_name"],
            "email": record["email"],
            "password": record["password"],
        }
        for record in DUMMY_USERS
    ]


def authenticate_user(email: str, password: str) -> User | None:
    with get_session() as session:
        user = session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None or not check_password_hash(user.password_hash, password):
            return None
        return user


def find_or_create_google_user(google_sub: str, email: str, full_name: str) -> User:
    """
    Find an existing user by Google subject ID or email, or create a new one.
    Links google_sub to an existing email-password account on first Google sign-in.
    """
    import secrets as _secrets

    with get_session() as session:
        # 1. Match by google_sub (fastest path for returning Google users)
        user = session.scalar(select(User).where(User.google_sub == google_sub))
        if user:
            return user

        # 2. Match by email — link google_sub to an existing account
        user = session.scalar(select(User).where(User.email == email.strip().lower()))
        if user:
            user.google_sub = google_sub
            return user

        # 3. New user — create account without a usable password
        user = User(
            full_name=full_name,
            email=email.strip().lower(),
            password_hash=generate_password_hash(_secrets.token_hex(32)),
            google_sub=google_sub,
        )
        session.add(user)
        session.flush()
        return user


def fetch_subscriptions(user_id: int) -> list[Subscription]:
    with get_session() as session:
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.category))
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.renewal_date.asc(), Subscription.name.asc())
        )
        return session.scalars(stmt).unique().all()


def fetch_subscription(subscription_id: int, user_id: int) -> Subscription | None:
    with get_session() as session:
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.category))
            .where(Subscription.id == subscription_id, Subscription.user_id == user_id)
        )
        return session.scalar(stmt)


def create_subscription(
    user_id: int,
    name: str,
    category_id: int,
    cost: float,
    billing_cycle: str,
    renewal_date: date,
    notes: str | None,
) -> Subscription:
    with get_session() as session:
        subscription = Subscription(
            user_id=user_id,
            name=name.strip(),
            category_id=category_id,
            cost=cost,
            billing_cycle=billing_cycle,
            renewal_date=renewal_date,
            notes=notes.strip() if notes else None,
        )
        session.add(subscription)
        session.flush()
        session.refresh(subscription)
        return subscription


def update_subscription(
    user_id: int,
    subscription_id: int,
    name: str,
    category_id: int,
    cost: float,
    billing_cycle: str,
    renewal_date: date,
    notes: str | None,
) -> bool:
    with get_session() as session:
        subscription = session.scalar(
            select(Subscription).where(
                Subscription.id == subscription_id, Subscription.user_id == user_id
            )
        )
        if subscription is None:
            return False
        subscription.name = name.strip()
        subscription.category_id = category_id
        subscription.cost = cost
        subscription.billing_cycle = billing_cycle
        subscription.renewal_date = renewal_date
        subscription.notes = notes.strip() if notes else None
        return True


def get_google_tokens(user_id: int) -> dict | None:
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None or not user.google_refresh_token:
            return None
        return {
            "access_token": user.google_access_token,
            "refresh_token": user.google_refresh_token,
            "expiry": user.google_token_expiry,
        }


def save_google_tokens(
    user_id: int,
    access_token: str,
    refresh_token: str | None,
    expiry: "datetime | None",
) -> None:
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            return
        user.google_access_token = access_token
        if refresh_token:
            user.google_refresh_token = refresh_token
        user.google_token_expiry = expiry


def clear_google_tokens(user_id: int) -> None:
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            return
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_token_expiry = None


def delete_subscription(user_id: int, subscription_id: int) -> bool:
    with get_session() as session:
        subscription = session.scalar(
            select(Subscription).where(
                Subscription.id == subscription_id, Subscription.user_id == user_id
            )
        )
        if subscription is None:
            return False
        session.delete(subscription)
        return True


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

_NOTIFICATION_RULES: list[tuple[int, str, str]] = [
    (7,  "7_days",        "{name} — Renews in 7 days (${cost:.2f})"),
    (1,  "1_day",         "{name} — Renews tomorrow (${cost:.2f})"),
    (0,  "renewal_day",   "{name} — Renews today (${cost:.2f})"),
    (-1, "after_renewal", "{name} — Payment processed (${cost:.2f})"),
]

_NOTIFICATION_ICONS = {
    "7_days":        "⏰",
    "1_day":         "⚠️",
    "renewal_day":   "🔔",
    "after_renewal": "✅",
}


def generate_notifications(user_id: int) -> None:
    """Idempotently create notification records for subscriptions due soon."""
    today = date.today()
    with get_session() as session:
        subs = session.scalars(
            select(Subscription).where(Subscription.user_id == user_id)
        ).all()
        for sub in subs:
            for days_before, ntype, msg_tmpl in _NOTIFICATION_RULES:
                fire_on = sub.renewal_date - timedelta(days=days_before)
                if fire_on != today:
                    continue
                exists = session.scalar(
                    select(Notification).where(
                        Notification.subscription_id == sub.id,
                        Notification.notification_type == ntype,
                        Notification.renewal_date == sub.renewal_date,
                    )
                )
                if exists is None:
                    session.add(Notification(
                        user_id=user_id,
                        subscription_id=sub.id,
                        subscription_name=sub.name,
                        notification_type=ntype,
                        message=msg_tmpl.format(name=sub.name, cost=sub.cost),
                        renewal_date=sub.renewal_date,
                        is_read=False,
                    ))


def get_notifications(user_id: int) -> list[Notification]:
    with get_session() as session:
        return session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(100)
        ).all()


def get_unread_count(user_id: int) -> int:
    with get_session() as session:
        return session.scalar(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        ) or 0


def mark_all_notifications_read(user_id: int) -> None:
    with get_session() as session:
        unread = session.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        ).all()
        for n in unread:
            n.is_read = True
