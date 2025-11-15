from __future__ import annotations

from datetime import datetime
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        description="Credit analysis toolkit for internal risk teams.",
    )

    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/", tags=["system"])
    def root() -> Dict[str, str]:
        return {
            "service": settings.PROJECT_NAME,
            "environment": settings.DEFAULT_ENVIRONMENT,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @application.get("/health", tags=["system"])
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
