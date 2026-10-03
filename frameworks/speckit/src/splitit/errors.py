"""Domain errors and handlers that render them as the contract's Error schema."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class DuplicateMemberNameError(ApiError):
    status_code = 409
    code = "duplicate_member_name"

    def __init__(self, message: str, field: str | None = "name"):
        super().__init__(message, field)


class ValidationFailedError(ApiError):
    status_code = 422
    code = "validation_error"


def error_body(code: str, message: str, field: str | None) -> dict:
    error = {"code": code, "message": message}
    if field is not None:
        error["field"] = field
    return {"error": error}


async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.field))


async def _handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = [part for part in first.get("loc", ()) if part != "body"]
    # Field name: first string in the location path (e.g. "amount", "participant_ids").
    field = next((str(part) for part in loc if isinstance(part, str)), None)
    message = first.get("msg", "invalid request")
    # Pydantic prefixes messages from custom validators with "Value error, "; drop it.
    message = message.removeprefix("Value error, ")
    if field is not None:
        message = f"{field}: {message}"
    return JSONResponse(status_code=422, content=error_body("validation_error", message, field))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation)
