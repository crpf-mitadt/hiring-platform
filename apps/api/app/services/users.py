from app.models import Role, User, UserRole
from app.schemas.users import UserCreate
from sqlalchemy import select
from sqlalchemy.orm import Session


def create_user(db: Session, data: UserCreate) -> User:
    user = User(email=str(data.email), full_name=data.full_name)
    user.roles = [UserRole(role=role) for role in data.roles]
    db.add(user)
    db.flush()
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.full_name)))


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "roles": [role.role for role in user.roles],
    }


def user_has_role(user: User, role: Role) -> bool:
    return any(user_role.role == role for user_role in user.roles)

