from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

from app.config import Settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS prompt_items (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    body TEXT NOT NULL,
    metadata_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'dismissed')),
    copy_count INTEGER NOT NULL DEFAULT 0 CHECK (copy_count >= 0),
    last_copied_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    dismissed_at TEXT,
    UNIQUE (source, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_prompt_items_status_seq
    ON prompt_items (status, seq);
"""


def open_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: Path) -> None:
    connection = open_connection(db_path)
    try:
        connection.executescript(SCHEMA)
    finally:
        connection.close()


def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    settings: Settings = request.app.state.settings
    connection = open_connection(settings.database_path)
    try:
        yield connection
    finally:
        connection.close()

