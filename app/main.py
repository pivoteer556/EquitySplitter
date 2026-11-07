import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.auth import ensure_secret_state, maybe_rotate_secrets

logger = logging.getLogger("equitysplitter.startup")

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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global rotation_task
    db = SessionLocal()
    try:
        ensure_secret_state(db)
        maybe_rotate_secrets(db)
    finally:
        db.close()
    rotation_task = asyncio.create_task(_rotation_loop())
    try:
        yield
    finally:
        if rotation_task is not None:
            rotation_task.cancel()
            rotation_task = None


app = FastAPI(title=settings.app_name, lifespan=lifespan)
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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ui", response_class=FileResponse)
def local_ui() -> FileResponse:
    return FileResponse(UI_PATH)
