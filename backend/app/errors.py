from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Raise to return HTTP 4xx with {"error": "<code>", "message": "<plain words>"}."""

    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content={"error": exc.code, "message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_request", "message": f"{where}: {first.get('msg', 'invalid')}".strip(": ")},
        )
