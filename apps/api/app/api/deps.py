from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.security import get_actor
from app.db.session import get_db
from app.models import User

DbDep = Annotated[Session, Depends(get_db)]


def current_actor(
    db: DbDep,
    x_actor_id: Annotated[str, Header(alias="X-Actor-Id")],
) -> User:
    return get_actor(db, x_actor_id)


ActorDep = Annotated[User, Depends(current_actor)]

