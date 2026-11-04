import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from worship_bot.observability import request_id_context

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        candidate = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
        request_id = candidate if re.fullmatch(r"[a-f0-9]{32}", candidate) else uuid4().hex
        token = request_id_context.set(request_id)
        started = perf_counter()
        status_code = 500
        response_started = False

        async def logged_send(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, logged_send)
        except Exception:
            logger.exception(
                "http.request_failed",
                extra={
                    "method": scope["method"],
                    "route": getattr(scope.get("route"), "path", "<unmatched>"),
                },
            )
            if not response_started:
                response = JSONResponse({"detail": "Внутренняя ошибка сервера"}, status_code=500)
                await response(scope, receive, logged_send)
                return
            raise
        finally:
            route = getattr(scope.get("route"), "path", "<unmatched>")
            level = (
                logging.ERROR
                if status_code >= 500
                else logging.WARNING
                if status_code >= 400
                else logging.DEBUG
                if route == "/health"
                else logging.INFO
            )
            logger.log(
                level,
                "http.request_completed",
                extra={
                    "method": scope["method"],
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            request_id_context.reset(token)
