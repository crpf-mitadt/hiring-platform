from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.errors import AuthenticationRequired, InvalidTransition
from app.db.base import utcnow
from app.models import Role, User, UserRole, UserSession
from sqlalchemy import select
from sqlalchemy.orm import Session

PASSWORD_ITERATIONS = 210_000
SESSION_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def create_candidate_account(db: Session, *, email: str, full_name: str, password: str) -> User:
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise InvalidTransition("An account already exists for this email")
    user = User(email=email, full_name=full_name, password_hash=hash_password(password))
    user.roles = [UserRole(role=Role.CANDIDATE)]
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationRequired("Invalid email or password")
    return user


def create_session(db: Session, user: User) -> tuple[UserSession, str]:
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    now = utcnow()
    session = UserSession(
        user=user,
        session_token_hash=_hash_session_token(token),
        created_at=now,
        expires_at=now + timedelta(hours=get_settings().session_ttl_hours),
    )
    db.add(session)
    db.flush()
    return session, token


def get_user_for_session_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session = db.scalar(
        select(UserSession).where(UserSession.session_token_hash == _hash_session_token(token))
    )
    if session is None or session.revoked_at is not None or _aware(session.expires_at) <= utcnow():
        return None
    return session.user


def revoke_session(db: Session, token: str | None) -> None:
    if not token:
        return
    session = db.scalar(
        select(UserSession).where(UserSession.session_token_hash == _hash_session_token(token))
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = utcnow()


def session_user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "roles": [role.role for role in user.roles],
    }


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
