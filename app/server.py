from fastapi import FastAPI

from app.api.v1.ticket_router import router as ticket_router

app = FastAPI(title="ticket-api")

app.include_router(ticket_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
