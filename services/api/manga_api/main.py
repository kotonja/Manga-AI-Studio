import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from manga_api.config import get_settings
from manga_api.observability import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    configure_logging,
    request_id_from_request,
)
from manga_api.routes import alpha, admin, commands, composition, consistency, demo, director, eval, exports, health, jobs, labs, layout, learning, lettering, pacing, panel_render, projects, providers, provenance, qa, story, versions


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(
        title="Manga AI Studio API",
        version="0.1.0",
        description="Backend API for AI-assisted manga project, page, panel, and render workflows.",
        debug=not settings.is_production,
    )

    app.add_middleware(RequestContextMiddleware, settings=settings)
    app.add_middleware(RateLimitMiddleware, enabled=settings.rate_limit_enabled, per_minute=settings.rate_limit_per_minute)
    app.add_middleware(RequestSizeLimitMiddleware, max_request_bytes=settings.max_request_bytes)
    if settings.allowed_hosts and "*" not in settings.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request_id_from_request(request)
        logging.getLogger("manga_api.error").exception(
            "unhandled exception",
            extra={"request_id": request_id},
        )
        detail = str(exc) if settings.should_expose_error_details else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={
                "detail": detail,
                "request_id": request_id,
            },
        )

    app.include_router(health.router)
    app.include_router(alpha.router)
    app.include_router(projects.router)
    app.include_router(commands.router)
    app.include_router(providers.router)
    app.include_router(jobs.router)
    app.include_router(panel_render.router)
    app.include_router(story.router)
    app.include_router(pacing.router)
    app.include_router(layout.router)
    app.include_router(learning.router)
    app.include_router(lettering.router)
    app.include_router(consistency.router)
    app.include_router(composition.router)
    app.include_router(qa.router)
    app.include_router(exports.router)
    app.include_router(provenance.router)
    app.include_router(versions.router)
    app.include_router(labs.router)
    app.include_router(demo.router)
    app.include_router(director.router)
    app.include_router(eval.router)
    app.include_router(admin.router)
    return app


app = create_app()
