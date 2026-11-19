from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.errors import AuthenticationRequired, InvalidTransition
from app.db.base import utcnow
from app.models import Application, ApplicationAccessSession, ApplicationAccessToken
from sqlalchemy import select
from sqlalchemy.orm import Session

TOKEN_BYTES = 32


def create_application_access_token(db: Session, application: Application) -> tuple[ApplicationAccessToken, str]:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = utcnow()
    access = ApplicationAccessToken(
        application=application,
        token_hash=hash_token(token),
        created_at=now,
        expires_at=now + timedelta(hours=get_settings().application_access_token_ttl_hours),
    )
    db.add(access)
    db.flush()
    return access, token


def exchange_application_access_token(
    db: Session,
    token: str,
    *,
    user_agent_hint: str | None = None,
) -> tuple[ApplicationAccessSession, str]:
    now = utcnow()
    access = db.scalar(select(ApplicationAccessToken).where(ApplicationAccessToken.token_hash == hash_token(token)))
    if (
        access is None
        or access.revoked_at is not None
        or access.exchanged_at is not None
        or _aware(access.expires_at) <= now
    ):
        raise AuthenticationRequired("Application access link is invalid or expired")
    access.exchanged_at = now
    session_token = secrets.token_urlsafe(TOKEN_BYTES)
    session = ApplicationAccessSession(
        application_id=access.application_id,
        session_token_hash=hash_token(session_token),
        created_at=now,
        expires_at=now + timedelta(hours=get_settings().application_access_session_ttl_hours),
        user_agent_hint=user_agent_hint,
    )
    db.add(session)
    db.flush()
    return session, session_token


def get_application_for_access_session(db: Session, session_token: str | None) -> Application:
    if not session_token:
        raise AuthenticationRequired("Application access required")
    session = db.scalar(
        select(ApplicationAccessSession).where(ApplicationAccessSession.session_token_hash == hash_token(session_token))
    )
    if session is None or session.revoked_at is not None or _aware(session.expires_at) <= utcnow():
        raise AuthenticationRequired("Application access session is invalid or expired")
    return session.application


def continuation_url(raw_token: str) -> str | None:
    settings = get_settings()
    if settings.environment != "development":
        return None
    return f"{settings.public_web_base_url.rstrip('/')}/application/continue?token={raw_token}"


def require_same_application(application: Application, application_id: str) -> None:
    if application.id != application_id:
        raise InvalidTransition("Application-scoped access cannot be used for another application")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
