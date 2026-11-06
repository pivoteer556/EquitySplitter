import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.auth import ensure_secret_state, maybe_rotate_secrets

logger = logging.getLogger("equitysplitter.startup")

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

UI_PATH = Path(__file__).parent / "ui" / "index.html"

logger.warning("Database target: %s", settings.redacted_database_target())
rotation_task: asyncio.Task | None = None


async def _rotation_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            maybe_rotate_secrets(db)
        finally:
            db.close()
        await asyncio.sleep(3600)


@app.on_event("startup")
async def startup() -> None:
    global rotation_task
    db = SessionLocal()
    try:
        ensure_secret_state(db)
        maybe_rotate_secrets(db)
    finally:
        db.close()
    rotation_task = asyncio.create_task(_rotation_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    global rotation_task
    if rotation_task is not None:
        rotation_task.cancel()
        rotation_task = None


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ui", response_class=FileResponse)
def local_ui() -> FileResponse:
    return FileResponse(UI_PATH)
