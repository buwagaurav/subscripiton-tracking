from __future__ import annotations

from flask import session

from subtrack.database.db import authenticate_user, fetch_user


def login_user(email: str, password: str):
    user = authenticate_user(email, password)
    if user is None:
        return None
    session["user_id"] = user.id
    session.modified = True
    return user


def logout_user() -> None:
    session.pop("user_id", None)


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return fetch_user(int(user_id))


def is_authenticated() -> bool:
    return current_user() is not None
