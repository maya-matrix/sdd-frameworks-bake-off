"""One error shape for every failure: {"error": {"code": ..., "message": ...}}."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


async def _handle_api_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ApiError)
    return _error_response(error.status, error.code, error.message)


async def _handle_validation_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    first = error.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part != "body")
    message = f"{field}: {first['msg']}" if field else first["msg"]
    return _error_response(400, "VALIDATION_ERROR", message)


async def _handle_http_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, HTTPException)
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(error.status_code, "HTTP_ERROR")
    return _error_response(error.status_code, code, str(error.detail))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(HTTPException, _handle_http_error)
