# 6주차 — 스케줄러 엔드포인트 + Docker + K8s CronJob

> 목표: 회사와 같은 배포 형태를 손으로 한 번 만들어 본다. "앱 안의 스케줄러" 대신 "밖에서 호출하는 CronJob" 이 왜 필요한지 눈으로 확인한다.
> 결과물: 컨테이너 이미지(266MB), 로컬 K8s 클러스터에 레플리카 2 개 + Mongo + 5 분마다 도는 CronJob.

## 만든 것

```
app/
├── models/db/snapshots.py          # SnapshotDoc: 특정 시각의 티켓 통계
├── models/api/snapshot_api.py
├── repositories/snapshot_repo.py   # insert / list (고치지 않음)
├── repositories/ticket_repo.py     # + count(), count_by(field)  ← aggregation
├── services/snapshot_service.py    # take(): 세어서 저장
└── api/v1/
    ├── scheduler_endpoint.py       # POST /scheduler/snapshots  (무인증, CronJob 용)
    └── snapshot_router.py          # GET  /snapshots            (ADMIN, 이력 조회)
Dockerfile                          # multi-stage (uv 로 설치 → slim 이미지로 복사)
.dockerignore
docker-compose.yml                  # mongo + app
k8s/
├── configmap.yaml                  # 비밀 아닌 설정 (MONGO_URI=mongodb://mongo:27017 …)
├── secret.yaml                     # JWT_SECRET (로컬용 더미)
├── mongo.yaml                      # PVC + Deployment + Service
├── deployment.yaml                 # replicas: 2, probes, envFrom
├── service.yaml                    # ClusterIP  http://ticket-api/
└── cronjob.yaml                    # */5 * * * *  curl -X POST http://ticket-api/scheduler/snapshots
```

## 전체 그림

```
┌──────────────────────── kind 클러스터 ─────────────────────────┐
│                                                                 │
│  CronJob (5분마다)                                              │
│    └─ Job → Pod[curl] ── POST http://ticket-api/scheduler/snapshots
│                                   │                             │
│                          Service "ticket-api" (ClusterIP :80)   │
│                            ├──→ Pod[api] replica 1  :8000       │
│                            └──→ Pod[api] replica 2  :8000  ← 둘 중 하나만 받는다
│                                      │                          │
│                          Service "mongo" (:27017)               │
│                            └──→ Pod[mongo] ── PVC mongo-data    │
└─────────────────────────────────────────────────────────────────┘
```

실측: CronJob 을 수동으로 한 번 실행했더니 레플리카 2 개 중 `z2sfv` 하나만 `POST /scheduler/snapshots 201` 로그를 남겼고, Mongo 에 스냅샷 1 건이 생겼다.

## 핵심 개념

### 1. 스케줄링을 앱 밖으로 빼는 이유

| 방식 | 레플리카 2 개면 | 스케줄 바꾸려면 |
| --- | --- | --- |
| 앱 안 (APScheduler 등) | **2 번 실행** (각 프로세스가 자기 타이머를 가짐) | 코드 수정 + 재배포 |
| 외부 CronJob → HTTP 호출 | **1 번 실행** (Service 가 하나에 전달) | `cronjob.yaml` 한 줄 |

앱 코드엔 "무엇을 하나"(`take_snapshot`) 만 있고, "언제 하나" 는 K8s 매니페스트에 있다. 회사 `scheduler_endpoint.py` 와 운영 CronJob 의 관계가 이것.

### 2. 무인증 경로의 보호는 네트워크가 한다

- `/scheduler/*` 는 `_NO_AUTH_PREFIXES` 로 미들웨어를 통과한다 (CronJob 은 로그인할 수 없다).
- 대신 Service 가 `ClusterIP` 라 클러스터 밖에서는 아예 닿지 않는다. 운영에서도 Ingress 에 `/scheduler` 를 노출하지 않는다.
- "인증으로 막을 것" 과 "네트워크로 막을 것" 을 구분하는 사고.

### 3. aggregation pipeline

```python
pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
cursor = await self._col.aggregate(pipeline)
```

- 문서를 단계(stage)별로 흘려보내며 가공. `$group` 은 SQL 의 `GROUP BY`. `"_id"` 에 묶을 기준, 나머지에 집계식.
- 결과를 `{"open": 3, "approved": 2}` dict 로 바꿔 돌려준다. 없는 상태는 서비스가 0 으로 채운다 (차트 키가 들쭉날쭉하지 않게).

### 4. Dockerfile — multi-stage

```
builder (uv 포함, 크다)  ──.venv 만 복사──▶  runtime (python:slim, 작다)
```

- 1 단계에서 `uv sync --frozen --no-dev` 로 `.venv` 를 만들고, 2 단계는 `.venv` + `app/` 만 가져온다. uv·캐시·빌드 도구는 안 들어간다 → 266MB.
- `COPY pyproject.toml uv.lock` 을 코드보다 먼저: 코드만 바뀌면 의존성 레이어는 캐시 → 재빌드 수 초.
- `useradd appuser` + `USER appuser`: root 로 돌리지 않는다.
- `--host 0.0.0.0`: 컨테이너 안에서 127.0.0.1 에 바인딩하면 밖에서 못 들어온다.
- `.dockerignore` 로 `.env`, `.venv`, `tests`, `docs` 제외 — 이미지가 작아지고 비밀이 안 샌다.
- `[tool.uv] package = false`: 이 프로젝트는 라이브러리가 아니라 앱. `uv init` 이 만든 `src/` 와 build-system 은 지웠다.

### 5. docker-compose 에서 호스트명

```yaml
MONGO_URI: mongodb://mongo:27017     # localhost 가 아니다
```

- 컨테이너마다 자기만의 `localhost` 가 있다. 앱 컨테이너의 `localhost:27017` 엔 아무것도 없다.
- compose 는 서비스 이름을 DNS 로 등록한다 → `mongo`. K8s 에선 Service 이름이 같은 역할.

### 6. K8s 오브젝트 6 종 (이 프로젝트에서 쓴 것)

| 오브젝트 | 한 줄 | 파일 |
| --- | --- | --- |
| ConfigMap | 비밀 아닌 환경변수 묶음 | configmap.yaml |
| Secret | 비밀 환경변수 묶음 (운영에선 git 에 안 둠) | secret.yaml |
| Deployment | "이 이미지를 N 개 띄우고 죽으면 다시" | deployment.yaml, mongo.yaml |
| Service | Pod 들 앞의 고정 이름/주소 + 분산 | service.yaml, mongo.yaml |
| PersistentVolumeClaim | Pod 이 죽어도 남는 디스크 | mongo.yaml |
| CronJob | 스케줄대로 Job(일회성 Pod) 생성 | cronjob.yaml |

### 7. deployment.yaml 에서 눈여겨볼 것

```yaml
replicas: 2
imagePullPolicy: Never          # kind 에 load 한 로컬 이미지 사용
envFrom: [configMapRef, secretRef]
readinessProbe: /health         # 준비 안 됐으면 트래픽 안 보냄
livenessProbe:  /health         # 죽었으면 재시작
resources: requests / limits    # 스케줄링 기준 / 상한
```

- `/health` 가 DB ping 을 하므로 "DB 연결 끊긴 Pod" 은 readiness 실패 → 트래픽에서 빠진다. 2 주차에 health 에 ping 을 넣어둔 게 여기서 쓰인다.

### 8. CronJob 옵션

```yaml
schedule: "*/5 * * * *"
concurrencyPolicy: Forbid        # 이전 실행이 안 끝났으면 겹치지 않음
successfulJobsHistoryLimit: 3    # 완료 Job 3 개만 보관
backoffLimit: 2                  # 실패 시 재시도 2 번
args: [-fsS, -X, POST, http://ticket-api/scheduler/snapshots]   # -f: 4xx/5xx 면 실패로
```

## 자주 쓰는 명령

```bash
# Docker
docker compose up -d --build        # 앱+DB
docker compose logs -f app
docker compose down                 # (데이터 유지)

# kind / kubectl   (kind 는 새 터미널에서 PATH 에 잡힘)
kind create cluster --name ticket-api
kind load docker-image ticket-api:local --name ticket-api    # 이미지 다시 빌드할 때마다
kubectl apply -f k8s/
kubectl get pods -o wide                       # 레플리카 2 개 확인
kubectl logs -l app=ticket-api --prefix -f     # 두 Pod 로그를 한 번에
kubectl create job --from=cronjob/ticket-snapshots snap-now   # CronJob 즉시 실행
kubectl logs job/snap-now
kubectl exec deploy/mongo -- mongosh --quiet ticket_api --eval 'db.snapshots.countDocuments({})'
kubectl port-forward svc/ticket-api 8080:80    # 내 PC 8080 → 클러스터 서비스 (브라우저로 /docs 보기)
kubectl rollout restart deployment/ticket-api  # 새 이미지 load 후 재시작
kind delete cluster --name ticket-api          # 전부 정리
```

## 용어 정리

| 용어 | 뜻 | 비유 |
| --- | --- | --- |
| 이미지 / 컨테이너 | 설계도 / 그 설계도로 띄운 실행체 | 클래스 / 인스턴스 |
| multi-stage build | 빌드용 이미지와 실행용 이미지를 분리 | `devDependencies` 를 배포본에서 빼기 |
| 레지스트리 | 이미지 저장소 (Docker Hub, ECR…) | npm registry |
| 클러스터 / 노드 / Pod | K8s 전체 / 서버 한 대 / 컨테이너 묶음 1 개 | — |
| 레플리카 | 같은 Pod 을 몇 개 띄우나 | — |
| kind | Docker 컨테이너 안에 K8s 노드를 띄우는 로컬 도구 | — |
| ClusterIP | 클러스터 안에서만 보이는 Service | 사내망 전용 주소 |
| probe | K8s 가 주기적으로 찌르는 헬스체크 | — |
| manifest | K8s 오브젝트를 적은 YAML | — |
| cron 표현식 | `분 시 일 월 요일`. `*/5 * * * *` = 5 분마다 | — |
| 멱등 CronJob | 몇 번 돌아도 안전한 작업 (스냅샷은 그냥 한 장 더) | — |

## 삽질 / 주의

- `uv init` 이 만든 `src/ticket_api` + build-system 이 남아 있으면 Docker 빌드에서 `uv sync` 가 프로젝트 자체를 설치하려다 실패한다 → `package = false` 로 전환하고 `src/` 삭제.
- kind 에 이미지를 `load` 하지 않으면 `ErrImageNeverPull`. 이미지를 다시 빌드하면 **다시 load + rollout restart**.
- 로컬 uvicorn(8000)과 compose 의 app(8000)이 같은 포트를 쓴다. 둘 중 하나만.
- `kubectl run … --rm -i` 가 찍는 "All commands and output … recorded" 문구는 kind 의 안내문이지 에러가 아니다.

## 회사와 대응

| 미니 프로젝트 | 회사 |
| --- | --- |
| `api/v1/scheduler_endpoint.py` | `drms/api/v1/scheduler_endpoint.py` |
| `k8s/cronjob.yaml` | 운영 K8s CronJob 매니페스트 |
| `snapshots` 컬렉션 | `compliance_snapshots`, `metrics_aggregates` |
| `Dockerfile` (uv multi-stage) | 회사 Dockerfile (빌드 도구는 다를 수 있음) |

## 로드맵 완료 — 다음은

6 주 로드맵이 끝났다. 다음 단계는 **학습 UI**(`web/`, React): 로그인·티켓·역할 체험·감사 로그·스냅샷 차트·시스템 구조·용어집을 한 화면에서, "이 요청이 어느 레이어를 지나는가" 를 보여주며 설명한다.
