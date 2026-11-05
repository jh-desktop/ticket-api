"""요청 추적 (학습용).

요청 하나가 미들웨어 → 라우터 → 의존성 → 서비스 → 리포지토리를 지나는 동안
각 지점이 `mark("...")` 를 남기면, trace_middleware(server.py) 가 응답 헤더 X-Trace 에 그 목록을 실어 준다.
학습 UI 는 이 헤더를 읽어 "이 요청이 어느 레이어를 지났나" 를 그린다.

구현: contextvars — 요청마다 독립된 리스트. 같은 서버에서 동시에 처리되는 다른 요청과 섞이지 않는다.
비용: 문자열 몇 개 append. APP_ENV=dev 에서만 헤더로 노출한다.
"""

import contextvars
import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

_steps: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("trace_steps", default=None)


def start() -> None:
    """요청 시작 시 새 리스트. (trace_middleware 가 부른다)"""
    _steps.set([])


def mark(step: str) -> None:
    """지금 지나는 지점을 기록. 추적 중이 아니면(스크립트·테스트 직접 호출) 조용히 무시."""
    steps = _steps.get()
    if steps is not None:
        steps.append(step)


def steps() -> list[str]:
    return list(_steps.get() or [])


# ── 클래스 데코레이터: 서비스/리포지토리의 public 메서드 호출을 자동 기록 ──────────

C = TypeVar("C", bound=type[Any])


def traced(layer: str) -> Callable[[C], C]:
    """`@traced("service")` 를 클래스에 붙이면 public 메서드가 호출될 때 'service:ClassName.method' 가 기록된다."""

    def decorate(cls: C) -> C:
        for name, attr in list(vars(cls).items()):
            if name.startswith("_") or not inspect.isfunction(attr):
                continue
            label = f"{layer}:{cls.__name__}.{name}"
            if inspect.iscoroutinefunction(attr):
                setattr(cls, name, _wrap_async(attr, label))
            else:
                setattr(cls, name, _wrap_sync(attr, label))
        return cls

    return decorate


def _wrap_async(fn: Callable[..., Awaitable[Any]], label: str) -> Callable[..., Awaitable[Any]]:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        mark(label)
        return await fn(*args, **kwargs)

    return wrapper


def _wrap_sync(fn: Callable[..., Any], label: str) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        mark(label)
        return fn(*args, **kwargs)

    return wrapper
