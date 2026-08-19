from app.models import Role
from app.schemas.common import ApiModel
from pydantic import EmailStr


class UserCreate(ApiModel):
    email: EmailStr
    full_name: str
    roles: list[Role]


class UserRead(ApiModel):
    id: str
    email: EmailStr
    full_name: str
    roles: list[Role]

