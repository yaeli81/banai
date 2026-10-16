from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import carpenter, chat, health, proposals, reference, voice
from app.api.errors import error_response
from app.config import get_settings

# A design is bounded by the schema caps; 512 KB leaves ample headroom for a request.
MAX_BODY_BYTES = 512 * 1024
# Recordings and the carpenter PDF (two 3D images) have their own caps.
BODY_LIMITS = {"/api/voice/transcribe": voice.MAX_AUDIO_BYTES, "/api/carpenter/pdf": carpenter.MAX_BODY_BYTES}


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
        limit = BODY_LIMITS.get(request.url.path, MAX_BODY_BYTES)
        if length is not None and (not length.isdigit() or int(length) > limit):
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
    app.include_router(voice.router)
    app.include_router(carpenter.router)
    return app


app = create_app()
