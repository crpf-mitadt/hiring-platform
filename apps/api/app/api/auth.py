from fastapi import APIRouter, Response

from app.api.deps import ActorDep, DbDep, SessionTokenDep
from app.core.config import get_settings
from app.schemas.users import LoginRequest, RegisterCandidateRequest, UserRead
from app.services.auth import (
    authenticate_user,
    create_candidate_account,
    create_session,
    revoke_session,
    session_user_payload,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead)
def api_register_candidate(db: DbDep, response: Response, data: RegisterCandidateRequest) -> dict:
    user = create_candidate_account(
        db,
        email=str(data.email),
        full_name=data.full_name,
        password=data.password,
    )
    _, token = create_session(db, user)
    _set_session_cookie(response, token)
    db.commit()
    return session_user_payload(user)


@router.post("/login", response_model=UserRead)
def api_login(db: DbDep, response: Response, data: LoginRequest) -> dict:
    user = authenticate_user(db, email=str(data.email), password=data.password)
    _, token = create_session(db, user)
    _set_session_cookie(response, token)
    db.commit()
    return session_user_payload(user)


@router.post("/logout")
def api_logout(db: DbDep, response: Response, token: SessionTokenDep) -> dict:
    revoke_session(db, token)
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserRead)
def api_me(actor: ActorDep) -> dict:
    return session_user_payload(actor)


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 60 * 60,
        path="/",
    )
