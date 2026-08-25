from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import applications, auth, dashboard, documents, health, jobs, screening_jobs, users
from app.core.config import get_settings
from app.core.errors import DomainError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(applications.router, prefix="/api")
    app.include_router(screening_jobs.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    return app


app = create_app()
