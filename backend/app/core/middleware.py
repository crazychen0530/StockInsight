"""ASGI request correlation and safe access/error logging."""

import logging
from time import perf_counter
from uuid import uuid4

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.core.logging import exception_summary, request_id_context

logger = logging.getLogger("stockinsight.http")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # IDs are server-generated; never echo arbitrary credentials from a caller's header.
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        started = perf_counter()
        response_started = False
        status = 500

        async def correlated_send(message: Message) -> None:
            nonlocal response_started, status
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message = dict(message)
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", request_id.encode("ascii"))]
            await send(message)

        try:
            await self.app(scope, receive, correlated_send)
        except Exception as exception:
            logger.error(
                "request_failed", extra={"event_data": {"exception": exception_summary(exception)}}
            )
            if response_started:
                raise RuntimeError("Response transmission failed") from None
            response = error_response(
                Request(scope), 500, "internal_error", "Internal server error"
            )
            await response(scope, receive, correlated_send)
        finally:
            route = scope.get("route")
            logger.info(
                "request_completed",
                extra={
                    "event_data": {
                        "method": scope.get("method"),
                        "route": getattr(route, "path", "<unmatched>"),
                        "status": status,
                        "duration_ms": round((perf_counter() - started) * 1000, 2),
                    }
                },
            )
            request_id_context.reset(token)
