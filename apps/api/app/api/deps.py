from typing import Annotated

from fastapi import Cookie, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AuthenticationRequired
from app.core.security import get_actor
from app.db.session import get_db
from app.models import User
from app.models.recruitment import Application
from app.services.application_access import get_application_for_access_session
from app.services.auth import get_user_for_session_token

DbDep = Annotated[Session, Depends(get_db)]
SessionTokenDep = Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)]
ApplicationAccessTokenDep = Annotated[str | None, Cookie(alias=get_settings().application_access_cookie_name)]


def current_actor(
    db: DbDep,
    session_token: SessionTokenDep = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> User:
    session_user = get_user_for_session_token(db, session_token)
    if session_user is not None:
        return session_user
    if x_actor_id:
        return get_actor(db, x_actor_id)
    raise AuthenticationRequired("Authentication required")


def development_actor(
    db: DbDep,
    x_actor_id: Annotated[str, Header(alias="X-Actor-Id")],
) -> User:
    return get_actor(db, x_actor_id)


ActorDep = Annotated[User, Depends(current_actor)]
DevelopmentActorDep = Annotated[User, Depends(development_actor)]


def current_application_access(
    db: DbDep,
    application_access_token: ApplicationAccessTokenDep = None,
) -> Application:
    return get_application_for_access_session(db, application_access_token)


ApplicationAccessDep = Annotated[Application, Depends(current_application_access)]
