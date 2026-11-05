"""로컬 개발용 샘플 데이터 투입.

실행:  uv run python -m app.scripts.seed

- 사용자 5명(역할별)을 upsert 하고, 그들이 만든 티켓·감사로그를 지운 뒤 다시 만든다 → 몇 번 돌려도 같은 결과.
- 티켓은 리포지토리에 직접 넣지 않고 **TicketService 를 통해** 만든다 → 권한 규칙·감사 로그가 실제와 똑같이 남는다.
- APP_ENV 가 dev/test 가 아니면 실행을 거부한다.
"""

import asyncio
import sys
from dataclasses import dataclass

from bson import ObjectId
from pymongo import AsyncMongoClient

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.db.users import Role, UserDoc
from app.repositories.audit_repo import AuditRepository
from app.repositories.ticket_repo import TicketRepository
from app.repositories.user_repo import UserRepository
from app.services.audit_service import AuditService
from app.services.ticket_service import TicketService

PASSWORD = "password123"

@dataclass(frozen=True)
class SeedUser:
    email: str
    role: Role
    groups: tuple[str, ...]

SEED_USERS: tuple[SeedUser, ...] = (
    SeedUser("admin@example.com", "ADMIN", ()),
    SeedUser("writer@example.com", "GROUP_WRITER", ("backend",)),
    SeedUser("reader@example.com", "GROUP_READER", ("backend",)),
    SeedUser("owner1@example.com", "OWNER", ("backend",)),
    SeedUser("owner2@example.com", "OWNER", ("mobile",)),
)

async def seed() -> None:
    settings = get_settings()
    if settings.app_env not in ("dev", "test"):
        sys.exit(f"refusing to seed: APP_ENV={settings.app_env!r} (dev/test only)")

    client: AsyncMongoClient[dict[str, object]] = AsyncMongoClient(settings.mongo_uri, tz_aware=True)
    db = client[settings.mongo_db_name]
    users_repo = UserRepository(db)
    tickets = TicketService(TicketRepository(db), AuditService(AuditRepository(db)))

    # 1) 사용자 upsert — 이미 있으면 역할·그룹만 맞춘다 (비밀번호는 유지)
    users: dict[str, UserDoc] = {}
    for su in SEED_USERS:
        existing = await users_repo.get_by_email(su.email)
        if existing is None:
            user = await users_repo.create(
                {"email": su.email, "password_hash": hash_password(PASSWORD), "role": su.role, "groups": list(su.groups)}
            )
            print(f"  + user   {su.email:<22} {su.role}")
        else:

            user = await users_repo.update_role(ObjectId(existing.id), role=su.role, groups=list(su.groups))
            assert user is not None
            print(f"  = user   {su.email:<22} {su.role} (exists)")
        users[su.email] = user

    # 2) 시드 사용자가 만든 티켓·감사로그 제거 (다른 데이터는 건드리지 않는다)
    seed_ids = [u.id for u in users.values()]
    old = await db["tickets"].find({"owner_id": {"$in": seed_ids}}, {"_id": 1}).to_list()
    old_ids = [str(d["_id"]) for d in old]
    await db["tickets"].delete_many({"owner_id": {"$in": seed_ids}})
    await db["audit_logs"].delete_many({"ticket_id": {"$in": old_ids}})
    print(f"  - removed {len(old_ids)} seeded ticket(s) and their audit logs")

    # 3) 티켓 생성 — 서비스를 통해서 (규칙 + 감사로그 그대로)
    admin, writer, owner1, owner2 = (users[e] for e in ("admin@example.com", "writer@example.com", "owner1@example.com", "owner2@example.com"))

    t1 = await tickets.create(owner1, {"title": "로그인 버튼이 Safari 에서 동작 안 함", "description": "클릭해도 반응 없음", "group_id": "backend"})
    t2 = await tickets.create(owner1, {"title": "다크 모드 지원", "description": None, "group_id": "backend"})
    t3 = await tickets.create(writer, {"title": "결제 API 타임아웃 30s → 10s", "description": "운영 장애 대응", "group_id": "backend"})
    t4 = await tickets.create(owner2, {"title": "모바일 푸시 알림 지연", "description": "최대 5분 지연 보고됨", "group_id": "mobile"})
    t5 = await tickets.create(admin, {"title": "전사 비밀번호 정책 변경", "description": "최소 12자", "group_id": "security"})

    await tickets.update(owner1, t1.id, {"description": "클릭해도 반응 없음. iOS 17 에서만 재현"})
    await tickets.approve(writer, t1.id)  # 같은 그룹 WRITER 가 승인
    await tickets.reject(admin, t4.id)  # ADMIN 이 반려
    await tickets.approve(admin, t5.id)
    print("  + 5 tickets (2 approved, 1 rejected, 2 open) with audit trail")
    _ = (t2, t3)

    await client.close()
    print(f"\nseeded db '{settings.mongo_db_name}'. all passwords: {PASSWORD}")

if __name__ == "__main__":
    asyncio.run(seed())
