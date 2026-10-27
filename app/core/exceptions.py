from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """서비스 레이어에서 던지는 모든 예외의 부모.

    서비스는 HTTP 를 모른다. "없다", "그 전이는 안 된다" 같은 도메인 사실만 말하고,
    그것을 404/409 같은 HTTP 응답으로 바꾸는 일은 아래 핸들러가 한다.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class InvalidTransitionError(AppError):
    status_code = 409
    code = "invalid_transition"


def register_exception_handlers(app: FastAPI) -> None:
    """AppError 계열이 라우터 밖으로 튀어나오면 통일된 JSON 으로 응답한다."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
