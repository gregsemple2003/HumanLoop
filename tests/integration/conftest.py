from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _find_free_localhost_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass(slots=True)
class LiveServerHandle:
    process: subprocess.Popen[str]
    port: int
    database_path: Path
    log_path: Path
    _output: str = field(default="", init=False)
    _stopped: bool = field(default=False, init=False)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> str:
        if self._stopped:
            return self._output

        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

        if self.process.stdout is not None:
            self._output += self.process.stdout.read()

        self._stopped = True
        return self._output


def _wait_for_healthcheck(server: LiveServerHandle) -> None:
    deadline = time.monotonic() + 15.0
    last_error = ""

    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            output = server.stop()
            raise RuntimeError(
                "Live HumanLoop server exited before it became healthy.\n"
                f"exit_code={server.process.returncode}\n"
                f"output:\n{output}"
            )

        try:
            response = httpx.get(f"{server.base_url}/healthz", timeout=0.5)
            if response.status_code == 200 and response.json() == {"status": "ok"}:
                return
        except Exception as exc:  # pragma: no cover - startup timing dependent
            last_error = str(exc)

        time.sleep(0.1)

    output = server.stop()
    raise RuntimeError(
        "Timed out waiting for the live HumanLoop server healthcheck.\n"
        f"base_url={server.base_url}\n"
        f"last_error={last_error}\n"
        f"output:\n{output}"
    )


@pytest.fixture
def live_server_factory(tmp_path: Path):
    started_servers: list[LiveServerHandle] = []

    def factory(
        name: str = "live-server",
        *,
        database_path: Path | None = None,
        log_path: Path | None = None,
    ) -> LiveServerHandle:
        runtime_root = tmp_path / name
        resolved_database_path = database_path or (runtime_root / "humanloop.db")
        resolved_log_path = log_path or (runtime_root / "logs" / "humanloop.log")
        port = _find_free_localhost_port()

        env = os.environ.copy()
        env.update(
            {
                "HUMANLOOP_HOST": "127.0.0.1",
                "HUMANLOOP_PORT": str(port),
                "HUMANLOOP_DATABASE_PATH": str(resolved_database_path),
                "HUMANLOOP_LOG_PATH": str(resolved_log_path),
                "HUMANLOOP_LOG_LEVEL": "INFO",
                "PYTHONUNBUFFERED": "1",
            }
        )

        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        server = LiveServerHandle(
            process=process,
            port=port,
            database_path=resolved_database_path,
            log_path=resolved_log_path,
        )
        _wait_for_healthcheck(server)
        started_servers.append(server)
        return server

    yield factory

    for server in reversed(started_servers):
        server.stop()


@pytest.fixture
def live_server(live_server_factory) -> LiveServerHandle:
    return live_server_factory()
