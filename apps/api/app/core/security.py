from app.core.config import get_settings
from app.core.errors import PermissionDenied
from app.models import Role, User
from sqlalchemy import select
from sqlalchemy.orm import Session


def role_values(user: User) -> set[Role]:
    return {role.role for role in user.roles}


def require_any_role(user: User, allowed: set[Role]) -> None:
    if role_values(user).isdisjoint(allowed):
        allowed_names = ", ".join(sorted(role.value for role in allowed))
        raise PermissionDenied(f"Requires one of: {allowed_names}")


def get_actor(db: Session, actor_id: str) -> User:
    settings = get_settings()
    if settings.actor_provider != "development":
        raise PermissionDenied("Configured actor provider is not implemented in this milestone")
    if settings.environment not in {"local", "test", "development"} and not settings.allow_development_actor_provider:
        raise PermissionDenied("Development X-Actor-Id provider is disabled for this environment")
    user = db.scalar(select(User).where(User.id == actor_id))
    if user is None:
        raise PermissionDenied("Unknown actor")
    return user


STAFF_ROLES = {
    Role.HR_RECRUITER,
    Role.DEPARTMENT_REVIEWER,
    Role.INTERVIEWER,
    Role.PROCTOR,
    Role.HIRING_ADMIN,
}
