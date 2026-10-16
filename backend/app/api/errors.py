"""The `{success, data, error}` envelope for errors, with engine-owned messages only."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from app.domain.errors import DomainError


def error_response(status: int, code: str, message: str, path: str | None = None) -> JSONResponse:
    error: dict = {"code": code, "message": message}
    if path is not None:
        error["path"] = path
    return JSONResponse(status_code=status, content={"success": False, "data": None, "error": error})


def domain_error_response(error: DomainError, status: int = 422) -> JSONResponse:
    return error_response(status, error.code, error.message, error.path)
