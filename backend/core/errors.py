"""API errors that carry a stable machine-readable code next to the human message.

Clients (the mobile app) localise by `code`; `detail` stays an English fallback.
Response body: {"detail": "...", "code": "INTENT_DUPLICATE", "params": {...}}
"""
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_DEFAULT_CODES = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 422: "INVALID_REQUEST",
                  429: "TOO_MANY_REQUESTS", 503: "SERVICE_UNAVAILABLE"}


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, params: dict | None = None):
        super().__init__(status_code, message)
        self.code = code
        self.params = params or {}


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    body = {"detail": exc.detail, "code": getattr(exc, "code", None) or _DEFAULT_CODES.get(exc.status_code, "ERROR")}
    if getattr(exc, "params", None):
        body["params"] = exc.params
    return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    return JSONResponse({"detail": f"Invalid request: {where} {first.get('msg', '')}".strip(), "code": "INVALID_REQUEST"}, status_code=422)
