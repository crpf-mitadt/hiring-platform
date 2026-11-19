from app.models import Role, User, UserRole
from sqlalchemy import select
from sqlalchemy.orm import Session

SYSTEM_EMAIL = "system@hiring-platform.local"


def get_system_actor(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == SYSTEM_EMAIL))
    if user is None:
        user = User(email=SYSTEM_EMAIL, full_name="Hiring Platform System")
        user.roles = [UserRole(role=Role.HIRING_ADMIN)]
        db.add(user)
        db.flush()
    return user
