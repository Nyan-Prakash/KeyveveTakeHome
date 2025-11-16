"""FastAPI application factory."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.destinations import router as destinations_router
from backend.app.api.health import get_health
from backend.app.api.knowledge import router as knowledge_router
from backend.app.api.plan import router as plan_router
from backend.app.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title="Keyveve Travel Advisor API",
        description="Agentic AI Travel Advisor - Backend API",
        version="0.1.0",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.ui_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        """Health check endpoint."""
        result = await get_health()
        return result.model_dump()

    # Include routers
    app.include_router(destinations_router)
    app.include_router(knowledge_router)
    app.include_router(plan_router)

    return app


# Create app instance for uvicorn
app = create_app()
