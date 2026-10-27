from typing import Annotated

from fastapi import Depends, FastAPI

from app.api.v1.ticket_router import router as ticket_router
from app.core.config import Settings, get_settings

app = FastAPI(title="ticket-api")

app.include_router(ticket_router)


@app.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
