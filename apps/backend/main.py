"""Reporter Pro — FastAPI entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PROJECT_ROOT.parents[1]
load_dotenv(REPOSITORY_ROOT / ".env")

from api.errors import install_error_handling
from api.routes import router as api_router
from api.routes import shutdown_report_scheduler
from core.config import (
    APP_NAME,
    APP_VERSION,
    automatic_backup_enabled,
    automatic_backup_interval_hours,
    automatic_backup_retention,
    cors_origins,
)
from core.database import close_db, get_db
from core.logging_config import configure_logging
from core.runtime_lifecycle import runtime_lifecycle
from core.scheduled_backup import ScheduledBackupManager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

FRONTEND_DIST = PROJECT_ROOT.parent / "frontend" / "dist"
configure_logging(PROJECT_ROOT / "data")
LOGGER = logging.getLogger("reporter.backup")
AUTO_BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
_auto_backups = ScheduledBackupManager(
    get_db,
    PROJECT_ROOT / "templates",
    AUTO_BACKUP_DIR,
    interval_hours=automatic_backup_interval_hours(),
    retention=automatic_backup_retention(),
    enabled=automatic_backup_enabled(),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("=" * 50)
    print(f"  {APP_NAME} v{APP_VERSION}")
    print("  API: http://127.0.0.1:8000/api/health")
    print("  Docs: http://127.0.0.1:8000/docs")
    print("=" * 50)
    print("", flush=True)

    async def monitor_launcher() -> None:
        while True:
            await asyncio.sleep(2)
            if runtime_lifecycle.launcher_expired():
                print(
                    "[Reporter Pro] Launcher heartbeat expired; stopping backend.",
                    flush=True,
                )
                os.kill(os.getpid(), signal.SIGTERM)
                return

    async def monitor_backups() -> None:
        # Keep startup responsive and avoid creating snapshots in short-lived probes.
        await asyncio.sleep(60)
        while True:
            try:
                result = await asyncio.to_thread(_auto_backups.run_if_due)
                if result.get("created"):
                    LOGGER.info(
                        "automatic_workspace_backup filename=%s removed=%s",
                        result.get("filename"),
                        len(result.get("removed") or []),
                    )
            except Exception:
                LOGGER.exception("automatic_workspace_backup_failed")
            await asyncio.sleep(60 * 60)

    monitor_task = asyncio.create_task(monitor_launcher())
    backup_task = asyncio.create_task(monitor_backups())
    try:
        yield
    finally:
        monitor_task.cancel()
        backup_task.cancel()
        with suppress(asyncio.CancelledError):
            await monitor_task
        with suppress(asyncio.CancelledError):
            await backup_task
        shutdown_report_scheduler(wait=True)
        close_db()
        runtime_lifecycle.reset()
        print("Reporter Pro shutting down...")


app = FastAPI(
    title=APP_NAME,
    description="Automated DFIR / Compromise Assessment Report Generator",
    version=APP_VERSION,
    lifespan=lifespan,
)

install_error_handling(app)

# CORS — local development origins only unless explicitly configured.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Disposition",
        "X-Backup-Schema",
        "X-Backup-Templates",
        "X-Docx-Fields",
        "X-Report-Integrity",
        "X-Report-Id",
        "X-Request-Signature",
        "X-Content-Signature",
        "X-Request-ID",
    ],
)

# API routes
app.include_router(api_router)

# Mount frontend build (production)
if FRONTEND_DIST.exists() and FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT)],
    )
