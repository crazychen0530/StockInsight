"""Application failures and HTTP exception mapping."""

import re
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.schemas.error import ErrorResponse, ValidationIssue


class ApplicationError(Exception):
    """Explicitly public service-layer failure; never pass internal exception text."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code) or not 400 <= status_code <= 599:
            raise ValueError("Invalid application error definition")
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: list[ValidationIssue] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        code=code,
        message=request.app.state.redactor.text(message),
        request_id=request.state.request_id,
        details=details,
    )
    return JSONResponse(body.model_dump(), status_code=status, headers=headers)


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def application_error(request: Request, exception: ApplicationError) -> JSONResponse:
        return error_response(request, exception.status_code, exception.code, exception.message)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exception: HTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed", 503: "service_unavailable"}
        try:
            message = HTTPStatus(exception.status_code).phrase
        except ValueError:
            message = "HTTP request failed"
        headers = {
            key: request.app.state.redactor.text(value)
            for key, value in (exception.headers or {}).items()
            if key.lower() in {"allow", "www-authenticate", "retry-after"}
            and "\n" not in value
            and "\r" not in value
        }
        return error_response(
            request,
            exception.status_code,
            codes.get(exception.status_code, "http_error"),
            message,
            headers=headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exception: RequestValidationError) -> JSONResponse:
        redactor = request.app.state.redactor
        details = [
            ValidationIssue(
                location=[
                    redactor.text(item)[:100] if isinstance(item, str) else item
                    for item in error["loc"][:16]
                ],
                type=error["type"],
            )
            for error in exception.errors()[:100]
        ]
        return error_response(
            request, 422, "validation_error", "Request validation failed", details
        )
