from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, health, proposals, reference
from app.api.errors import error_response
from app.config import get_settings

# A design is bounded by the schema caps; 512 KB leaves ample headroom for a request.
MAX_BODY_BYTES = 512 * 1024


def create_app() -> FastAPI:
    settings = get_settings()
    is_production = settings.app_env == "production"
    app = FastAPI(
        title="BanAI Wardrobe Designer API",
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type", "If-Match"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        length = request.headers.get("content-length")
        if length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
            return error_response(413, "TOO_LARGE", "The request is too large.")
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError):
        # Never echo the (untrusted) input back.
        return error_response(422, "INVALID_REQUEST", "The request is not valid.")

    app.include_router(health.router)
    app.include_router(reference.router)
    app.include_router(chat.router)
    app.include_router(proposals.router)
    return app


app = create_app()
