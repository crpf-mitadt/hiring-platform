from fastapi import APIRouter

from app.api.deps import DbDep
from app.schemas.users import UserCreate, UserRead
from app.services.users import create_user, list_users, serialize_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead)
def api_create_user(db: DbDep, data: UserCreate) -> dict:
    user = create_user(db, data)
    db.commit()
    return serialize_user(user)


@router.get("", response_model=list[UserRead])
def api_list_users(db: DbDep) -> list[dict]:
    return [serialize_user(user) for user in list_users(db)]

