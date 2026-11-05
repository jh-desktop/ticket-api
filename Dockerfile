# ── 1단계: 의존성 설치 (빌드 도구가 있는 큰 이미지) ─────────────────────────────
# uv 가 내장된 공식 이미지. 여기서 .venv 를 만든다.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 의존성 파일만 먼저 복사 → 코드가 바뀌어도 이 레이어는 캐시돼서 재설치하지 않는다
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ── 2단계: 실행 (파이썬만 있는 작은 이미지) ───────────────────────────────────
FROM python:3.11-slim-bookworm

WORKDIR /app

# root 로 돌리지 않는다 — 컨테이너가 뚫려도 피해를 줄이기 위해
RUN useradd --create-home --uid 1000 appuser

# 1단계에서 만든 .venv 와 애플리케이션 코드만 가져온다 (uv, 캐시, 빌드 도구는 안 가져옴)
COPY --from=builder /app/.venv /app/.venv
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000

# 컨테이너 안에서는 127.0.0.1 이 아니라 0.0.0.0 에 바인딩해야 밖(호스트/다른 컨테이너)에서 접근 가능
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
