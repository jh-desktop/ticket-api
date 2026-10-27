"""역할(Role) + 그룹 스코핑 규칙. 권한 판단은 전부 이 파일에만 둔다.

역할 4종
- ADMIN        : 모든 그룹의 모든 티켓을 보고, 고치고, 승인/반려한다.
- GROUP_WRITER : 자기 그룹(groups)의 티켓을 보고, 만들고, 승인/반려한다.
- GROUP_READER : 자기 그룹의 티켓을 보기만 한다.
- OWNER        : 자기가 만든 티켓만 보고 고친다. 승인/반려는 못 한다.

두 가지 형태로 쓰인다
1. 조회: scope_filter(user) 가 Mongo 필터를 돌려준다 → "볼 수 있는 것만" 쿼리에 섞인다.
2. 행위: can_*(user, ticket) 가 True/False → 서비스가 ForbiddenError 로 바꾼다.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from app.core.auth import CurrentUser
from app.core.exceptions import ForbiddenError
from app.models.db.tickets import TicketDoc
from app.models.db.users import Role, UserDoc

# ---- 1. 조회 필터 ------------------------------------------------------------


def scope_filter(user: UserDoc) -> dict[str, Any]:
    """이 사용자가 볼 수 있는 티켓만 남기는 Mongo 필터. 인가 결과가 '허용/거부' 가 아니라 '쿼리 조건' 으로 나타난다."""
    if user.role == "ADMIN":
        return {}
    if user.role in ("GROUP_WRITER", "GROUP_READER"):
        return {"group_id": {"$in": user.groups}}
    return {"owner_id": user.id}  # OWNER


# ---- 2. 행위별 판단 -----------------------------------------------------------


def can_view(user: UserDoc, ticket: TicketDoc) -> bool:
    if user.role == "ADMIN":
        return True
    if user.role in ("GROUP_WRITER", "GROUP_READER"):
        return ticket.group_id in user.groups
    return ticket.owner_id == user.id


def can_create(user: UserDoc, group_id: str) -> bool:
    if user.role == "ADMIN":
        return True
    if user.role in ("GROUP_WRITER", "OWNER"):
        return group_id in user.groups
    return False  # GROUP_READER


def can_edit(user: UserDoc, ticket: TicketDoc) -> bool:
    """제목·설명 수정, 삭제. 관리자이거나 본인이 만든 티켓."""
    return user.role == "ADMIN" or ticket.owner_id == user.id


def can_transition(user: UserDoc, ticket: TicketDoc) -> bool:
    """승인/반려. 관리자이거나, 그 그룹의 GROUP_WRITER."""
    if user.role == "ADMIN":
        return True
    return user.role == "GROUP_WRITER" and ticket.group_id in user.groups


def ensure(allowed: bool, message: str) -> None:
    """서비스에서 `ensure(can_edit(user, ticket), "...")` 처럼 한 줄로 쓰기 위한 도우미."""
    if not allowed:
        raise ForbiddenError(message)


# ---- 3. 라우터용 의존성 --------------------------------------------------------


def require_role(*roles: Role) -> Callable[..., Coroutine[Any, Any, UserDoc]]:
    """`Depends(require_role("ADMIN", "GROUP_WRITER"))` — 역할이 아니면 403, 맞으면 사용자 반환.

    세밀한 판단(어느 그룹의 티켓인가)은 서비스에서 하고, 여기선 '역할 자체가 아예 안 되는' 요청을 입구에서 막는다.
    """

    async def _dependency(user: CurrentUser) -> UserDoc:
        if user.role not in roles:
            raise ForbiddenError(f"Requires one of roles: {', '.join(roles)}")
        return user

    return _dependency
