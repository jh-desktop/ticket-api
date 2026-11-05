"""학습 UI 전용 엔드포인트 (/learn/*). 인증 없음, APP_ENV=dev 에서만 동작.

- /learn/docs            docs/*.md 목록
- /learn/docs/{name}     문서 본문 (UI 가 렌더링)
- /learn/glossary        docs 의 "용어 정리" 표를 모아 JSON 으로
- /learn/structure       레이어·파일·요청 흐름 설명 (시스템 구조 화면)

docs/ 는 Docker 이미지에 넣지 않으므로 운영 컨테이너에서는 빈 목록이 나온다 — 의도된 동작.
"""

import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.models.api.learn_api import (
    DocContent,
    DocSummary,
    FileInfo,
    GlossaryEntry,
    LayerInfo,
    StructureResponse,
)

router = APIRouter(prefix="/learn", tags=["learn"])

_DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"
_DOC_NAME = re.compile(r"^[a-z0-9_-]+$")


def _dev_only(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    if settings.app_env != "dev":
        raise NotFoundError("Not available outside dev")


DevOnly = Depends(_dev_only)


def _title_of(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _read_doc(name: str) -> tuple[str, str]:
    if not _DOC_NAME.match(name):
        raise NotFoundError(f"Doc {name!r} not found")
    path = _DOCS_DIR / f"{name}.md"
    if not path.is_file():
        raise NotFoundError(f"Doc {name!r} not found")
    md = path.read_text(encoding="utf-8")
    return _title_of(md, name), md


@router.get("/docs", response_model=list[DocSummary], dependencies=[DevOnly])
async def list_docs() -> list[DocSummary]:
    out: list[DocSummary] = []
    if not _DOCS_DIR.is_dir():
        return out
    for p in sorted(_DOCS_DIR.glob("*.md")):
        title, _ = _read_doc(p.stem)
        out.append(DocSummary(name=p.stem, title=title))
    return out


@router.get("/docs/{name}", response_model=DocContent, dependencies=[DevOnly])
async def get_doc(name: str):
    title, md = _read_doc(name)
    return DocContent(name=name, title=title, markdown=md)


_GLOSSARY_HEADER = re.compile(r"^\|\s*용어\s*\|")


@router.get("/glossary", response_model=list[GlossaryEntry], dependencies=[DevOnly])
async def glossary():
    """각 주차 문서의 '| 용어 | 뜻 | 프론트 대응 |' 표를 긁어 모은다."""
    entries: list[GlossaryEntry] = []
    if not _DOCS_DIR.is_dir():
        return entries
    for p in sorted(_DOCS_DIR.glob("*.md")):
        lines = p.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            if _GLOSSARY_HEADER.match(lines[i]):
                i += 2  # 헤더 + 구분선(|---|---|)
                while i < len(lines) and lines[i].startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if len(cells) >= 2 and cells[0]:
                        entries.append(
                            GlossaryEntry(
                                term=cells[0].replace("`", ""),
                                meaning=cells[1],
                                frontend=(cells[2] if len(cells) > 2 and cells[2] not in ("—", "-") else ""),
                                source=p.stem,
                            )
                        )
                    i += 1
            i += 1
    return entries


_LAYERS: list[LayerInfo] = [
    LayerInfo(
        key="middleware", name="미들웨어", folder="app/server.py",
        role="모든 요청이 지나는 관문. 토큰이 있고 멀쩡한지만 본다.",
        knows=["쿠키/헤더의 토큰", "_NO_AUTH_PATHS 예외 목록"], never=["누구인지(DB)", "무엇을 할 수 있는지"],
        company="drms/server.py", files=["app/server.py"],
    ),
    LayerInfo(
        key="router", name="라우터", folder="app/api/v1/",
        role="HTTP 를 받아 서비스에 넘기고, 결과를 응답 모양으로 바꾼다. 판단하지 않는다.",
        knows=["경로·메서드·상태코드", "요청/응답 스키마(models/api)", "Depends 로 무엇을 주입받을지"], never=["비즈니스 규칙", "Mongo 문법"],
        company="drms/api/v1/*_router.py",
        files=["app/api/v1/auth_router.py", "app/api/v1/ticket_router.py", "app/api/v1/audit_router.py", "app/api/v1/user_router.py", "app/api/v1/snapshot_router.py", "app/api/v1/scheduler_endpoint.py"],
    ),
    LayerInfo(
        key="auth", name="인증·인가 의존성", folder="app/core/auth.py, app/core/rbac.py",
        role="get_current_user 가 '누구인가' 를, rbac 가 '해도 되나' 를 판단한다.",
        knows=["JWT 검증", "역할 4종 + 그룹 스코핑"], never=["티켓 규칙 자체"],
        company="drms/core/auth.py, drms/core/rbac.py", files=["app/core/auth.py", "app/core/rbac.py"],
    ),
    LayerInfo(
        key="service", name="서비스", folder="app/services/",
        role="비즈니스 규칙. 상태 전이, 권한 확인, 감사 로그 호출. HTTP 도 Mongo 도 모른다.",
        knows=["되는 일 / 안 되는 일", "다른 서비스 호출(감사 로그)"], never=["상태코드", "find_one, $set"],
        company="drms/services/*_service.py",
        files=["app/services/ticket_service.py", "app/services/audit_service.py", "app/services/auth_service.py", "app/services/user_service.py", "app/services/snapshot_service.py"],
    ),
    LayerInfo(
        key="repository", name="리포지토리", folder="app/repositories/",
        role="Mongo 쿼리 전부. 규칙은 모른다. 서비스가 준 필터를 그대로 쿼리에 섞는다.",
        knows=["insert_one, find, $set, aggregate", "인덱스"], never=["권한", "상태 전이"],
        company="drms/repositories/*_repo.py",
        files=["app/repositories/ticket_repo.py", "app/repositories/audit_repo.py", "app/repositories/user_repo.py", "app/repositories/snapshot_repo.py"],
    ),
    LayerInfo(
        key="db", name="MongoDB", folder="app/core/db.py",
        role="컬렉션: tickets, audit_logs, users, snapshots. 연결은 앱 전체에 하나.",
        knows=["문서(JSON 비슷한 것) 저장"], never=["타입 검증(그건 Pydantic)"],
        company="같은 Mongo", files=["app/core/db.py", "app/models/db/tickets.py", "app/models/db/audit_logs.py", "app/models/db/users.py", "app/models/db/snapshots.py"],
    ),
]

_FILES: list[FileInfo] = [
    FileInfo(path="app/server.py", layer="middleware", summary="앱 생성, 미들웨어(인증·추적·CORS), 라우터 등록, lifespan(DB 연결)", company="drms/server.py"),
    FileInfo(path="app/core/config.py", layer="db", summary=".env → Settings 객체 (pydantic-settings)"),
    FileInfo(path="app/core/db.py", layer="db", summary="AsyncMongoClient 1개, get_db 의존성, Document/MongoDB 타입 별칭"),
    FileInfo(path="app/core/auth.py", layer="auth", summary="JWT 발급·검증, HttpOnly 쿠키 심기, get_current_user", company="drms/core/auth.py"),
    FileInfo(path="app/core/rbac.py", layer="auth", summary="scope_filter(조회 필터), can_*(행위 판단), require_role", company="drms/core/rbac.py"),
    FileInfo(path="app/core/security.py", layer="auth", summary="bcrypt 해시·검증"),
    FileInfo(path="app/core/exceptions.py", layer="router", summary="AppError 계열 + {error:{code,message}} 응답 핸들러"),
    FileInfo(path="app/core/trace.py", layer="middleware", summary="요청이 지난 레이어 기록 → X-Trace 헤더 (학습용)"),
    FileInfo(path="app/core/clock.py", layer="db", summary="utcnow(): Mongo 정밀도(ms)에 맞춘 시각"),
    FileInfo(path="app/api/v1/auth_router.py", layer="router", summary="signup / login(Set-Cookie) / logout / me"),
    FileInfo(path="app/api/v1/ticket_router.py", layer="router", summary="티켓 CRUD + approve/reject. 전부 한 줄: svc 호출", company="drms/api/v1/cr_router.py"),
    FileInfo(path="app/api/v1/audit_router.py", layer="router", summary="GET /audit-logs (ADMIN)", company="drms/api/v1/audit_router.py"),
    FileInfo(path="app/api/v1/user_router.py", layer="router", summary="GET /users, PATCH /users/{id}/role (ADMIN)"),
    FileInfo(path="app/api/v1/snapshot_router.py", layer="router", summary="GET /snapshots (ADMIN) — 통계 이력"),
    FileInfo(path="app/api/v1/scheduler_endpoint.py", layer="router", summary="POST /scheduler/snapshots — 외부 CronJob 이 호출, 무인증", company="drms/api/v1/scheduler_endpoint.py"),
    FileInfo(path="app/api/v1/learn_router.py", layer="router", summary="이 학습 UI 가 쓰는 문서·용어집·구조 API (dev 전용)"),
    FileInfo(path="app/services/ticket_service.py", layer="service", summary="상태 전이 표, rbac 호출, 감사 로그 기록", company="drms/services/cr_service.py"),
    FileInfo(path="app/services/audit_service.py", layer="service", summary="record() / list()"),
    FileInfo(path="app/services/auth_service.py", layer="service", summary="signup(첫 사용자 ADMIN) / login(해시 비교 → 토큰)"),
    FileInfo(path="app/services/user_service.py", layer="service", summary="역할·그룹 부여"),
    FileInfo(path="app/services/snapshot_service.py", layer="service", summary="take(): 상태별·그룹별 개수 세어 저장"),
    FileInfo(path="app/repositories/ticket_repo.py", layer="repository", summary="tickets 컬렉션 CRUD, count_by(aggregate)", company="drms/repositories/cr_repo.py"),
    FileInfo(path="app/repositories/audit_repo.py", layer="repository", summary="audit_logs insert/list (수정·삭제 없음)"),
    FileInfo(path="app/repositories/user_repo.py", layer="repository", summary="users, email unique 인덱스"),
    FileInfo(path="app/repositories/snapshot_repo.py", layer="repository", summary="snapshots insert/list"),
    FileInfo(path="app/models/api/ticket_api.py", layer="router", summary="TicketCreate / TicketUpdate / TicketResponse (요청·응답 모양)"),
    FileInfo(path="app/models/db/tickets.py", layer="db", summary="TicketDoc (DB 에 저장된 모양), TicketStatus, ObjectIdStr", company="drms/models/db/change_requests.py"),
    FileInfo(path="app/models/db/audit_logs.py", layer="db", summary="AuditLogDoc, AuditAction", company="drms/models/db/audit_logs.py"),
    FileInfo(path="app/models/db/users.py", layer="db", summary="UserDoc (password_hash 포함 — 응답엔 절대 안 나감), Role"),
    FileInfo(path="app/models/db/snapshots.py", layer="db", summary="SnapshotDoc", company="drms/models/db/compliance_snapshots.py"),
    FileInfo(path="app/scripts/seed.py", layer="service", summary="샘플 데이터. 서비스를 거쳐 넣어 감사 로그까지 실제처럼"),
    FileInfo(path="tests/conftest.py", layer="router", summary="테스트 DB 분리, 역할별 사용자 fixture 체인"),
    FileInfo(path="Dockerfile", layer="middleware", summary="multi-stage: uv 로 .venv 빌드 → python:slim 에 복사"),
    FileInfo(path="k8s/cronjob.yaml", layer="middleware", summary="5분마다 curl -X POST http://ticket-api/scheduler/snapshots", company="운영 K8s CronJob"),
]


@router.get("/structure", response_model=StructureResponse, dependencies=[DevOnly])
async def structure():
    return StructureResponse(
        layers=_LAYERS,
        files=_FILES,
        request_flow=["middleware", "router", "auth", "service", "repository", "db"],
    )
