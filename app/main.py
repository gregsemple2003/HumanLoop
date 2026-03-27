from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.inbox import router as inbox_router
from app.api.prompts import router as prompts_router
from app.config import Settings
from app.db import initialize_database
from app.models import HealthzResponse

LOGGER = logging.getLogger("humanloop")
STATIC_DIRECTORY = Path(__file__).resolve().parent / "static"


def configure_logging(level_name: str, log_path: Path) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
        force=True,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(
            resolved_settings.log_level,
            resolved_settings.log_path,
        )
        initialize_database(resolved_settings.database_path)
        LOGGER.info(
            "HumanLoop database ready at %s",
            resolved_settings.database_path,
        )
        LOGGER.info("HumanLoop logs writing to %s", resolved_settings.log_path)
        yield

    app = FastAPI(
        title="HumanLoop",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIRECTORY)),
        name="static",
    )
    app.include_router(inbox_router)
    app.include_router(prompts_router)

    @app.get("/healthz", response_model=HealthzResponse)
    def healthz() -> HealthzResponse:
        return HealthzResponse()

    return app


app = create_app()


def run() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    run()
