"""외부 스케줄러가 호출하는 엔드포인트 모음.

왜 앱 안에서 주기 실행(APScheduler 등)하지 않고 밖에서 호출하게 하나:
- 운영에서 앱은 레플리카 N 개로 뜬다. 앱 안의 스케줄러는 N 번 실행된다.
- 외부 CronJob 이 HTTP 로 1 번 호출하면 어느 레플리카든 하나만 처리한다.
- 스케줄(몇 분마다)은 K8s 매니페스트(k8s/cronjob.yaml)에 있고, 앱 코드엔 "무엇을 하나" 만 있다.

인증: 이 경로(/scheduler/*)는 server.py 의 _NO_AUTH_PREFIXES 로 미들웨어를 통과한다.
CronJob 은 로그인할 수 없기 때문. 대신 클러스터 안에서만 접근 가능하게 네트워크로 보호한다
(Service 는 ClusterIP, Ingress 에 /scheduler 를 노출하지 않음).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.models.api.snapshot_api import SnapshotResponse
from app.services.snapshot_service import SnapshotService, get_snapshot_service

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

Service = Annotated[SnapshotService, Depends(get_snapshot_service)]


@router.post("/snapshots", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
async def take_snapshot(svc: Service):
    """현재 티켓 통계를 한 장 저장한다. K8s CronJob 이 주기적으로 호출."""
    return await svc.take()
