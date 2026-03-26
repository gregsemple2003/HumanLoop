from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "runtime" / "humanloop.db"


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    database_path: Path = DEFAULT_DATABASE_PATH
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("HUMANLOOP_HOST", "127.0.0.1"),
            port=int(os.getenv("HUMANLOOP_PORT", "8000")),
            database_path=Path(
                os.getenv("HUMANLOOP_DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
            ).expanduser(),
            log_level=os.getenv("HUMANLOOP_LOG_LEVEL", "INFO"),
        )

