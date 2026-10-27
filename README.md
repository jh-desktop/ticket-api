# ticket-api

FastAPI + Pydantic v2 + MongoDB(pymongo AsyncMongoClient) 백엔드 학습 프로젝트.
회사 백엔드 구조를 그대로 축소해 만드는 중.

## 진행 상황

| 주차 | 주제 | 상태 |
| --- | --- | --- |
| 1 | FastAPI + Pydantic + Depends → 인메모리 티켓 CRUD | ✅ [정리](docs/week1.md) |
| 2 | MongoDB + 리포지토리 레이어 | ✅ [정리](docs/week2.md) |
| 3 | 서비스 레이어 + 에러 처리 + 감사 로그 | ✅ [정리](docs/week3.md) |
| 4 | JWT 인증 + RBAC | ✅ [정리](docs/week4.md) |
| 5 | 테스트 + 타입체크 + 시드 | ⬜ |
| 6 | 스케줄러 + Docker + K8s | ⬜ |

## 실행

```bash
uv sync                                   # 의존성 설치 (.venv 생성)
cp .env.example .env                      # 환경변수 파일 준비
uv run uvicorn app.server:app --reload    # http://localhost:8000/docs
```

## 학습 방식

- 프론트 개발자(React)가 백엔드를 배우는 프로젝트
- 회사 구조(api / services / repositories / models / core)를 그대로 따라감
- 주차별 정리는 `docs/` 폴더
