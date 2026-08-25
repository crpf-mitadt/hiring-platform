from fastapi import APIRouter

from app.api.deps import ActorDep, DbDep
from app.core.security import require_any_role
from app.models import Role
from app.schemas.users import UserCreate, UserRead
from app.services.users import create_user, list_users, serialize_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead)
def api_create_user(db: DbDep, actor: ActorDep, data: UserCreate) -> dict:
    require_any_role(actor, {Role.HIRING_ADMIN})
    user = create_user(db, data)
    db.commit()
    return serialize_user(user)


@router.get("", response_model=list[UserRead])
def api_list_users(db: DbDep, actor: ActorDep) -> list[dict]:
    require_any_role(actor, {Role.HIRING_ADMIN, Role.HR_RECRUITER})
    return [serialize_user(user) for user in list_users(db)]
