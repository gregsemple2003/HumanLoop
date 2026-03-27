from __future__ import annotations

import ctypes
import json
import sys
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import uvicorn

from app.config import Settings
from app.main import create_app

DESKTOP_APP_ID = "HumanLoop.Desktop"
DESKTOP_APP_NAME = "HumanLoop Desktop"
DESKTOP_POLL_INTERVAL_MS = 5000
HEALTHCHECK_PATH = "/healthz"
INBOX_PATH = "/inbox"
QUEUE_SUMMARY_PATH = "/api/prompts/summary"
ICON_DIRECTORY = Path(__file__).resolve().parent / "static" / "icons"
IDLE_ICON_PATH = ICON_DIRECTORY / "humanloop-desktop-idle.ico"
ALERT_ICON_PATH = ICON_DIRECTORY / "humanloop-desktop-alert.ico"
IDLE_ICON_PNG_PATHS = [
    ICON_DIRECTORY / "humanloop-desktop-idle-32.png",
    ICON_DIRECTORY / "humanloop-desktop-idle-64.png",
    ICON_DIRECTORY / "humanloop-desktop-idle-128.png",
]
ALERT_ICON_PNG_PATHS = [
    ICON_DIRECTORY / "humanloop-desktop-alert-32.png",
    ICON_DIRECTORY / "humanloop-desktop-alert-64.png",
    ICON_DIRECTORY / "humanloop-desktop-alert-128.png",
]
FLASHW_STOP = 0x0000
FLASHW_TRAY = 0x0002


class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("dwFlags", wintypes.DWORD),
        ("uCount", wintypes.UINT),
        ("dwTimeout", wintypes.DWORD),
    ]


@dataclass(frozen=True, slots=True)
class QueueSummary:
    pending_count: int
    latest_pending_seq: int | None
    current_prompt_id: str | None = None
    current_prompt_seq: int | None = None
    current_prompt_source: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "QueueSummary":
        current_prompt = payload.get("current_prompt")
        current_prompt_id: str | None = None
        current_prompt_seq: int | None = None
        current_prompt_source: str | None = None

        if isinstance(current_prompt, dict):
            prompt_id = current_prompt.get("id")
            prompt_seq = current_prompt.get("seq")
            prompt_source = current_prompt.get("source")
            if isinstance(prompt_id, str):
                current_prompt_id = prompt_id
            if isinstance(prompt_seq, int):
                current_prompt_seq = prompt_seq
            if isinstance(prompt_source, str):
                current_prompt_source = prompt_source

        latest_pending_seq = payload.get("latest_pending_seq")
        return cls(
            pending_count=int(payload.get("pending_count", 0)),
            latest_pending_seq=(
                int(latest_pending_seq)
                if isinstance(latest_pending_seq, int)
                else None
            ),
            current_prompt_id=current_prompt_id,
            current_prompt_seq=current_prompt_seq,
            current_prompt_source=current_prompt_source,
        )


class DesktopServerHandle:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._owns_server = False

    @property
    def base_url(self) -> str:
        return f"http://{self._settings.host}:{self._settings.port}"

    def ensure_running(self) -> None:
        if wait_for_healthcheck(self.base_url, timeout_seconds=0.75):
            return

        app = create_app(self._settings)
        config = uvicorn.Config(
            app,
            host=self._settings.host,
            port=self._settings.port,
            log_level=self._settings.log_level.lower(),
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._server.install_signal_handlers = lambda: None
        self._thread = threading.Thread(
            target=self._server.run,
            name="humanloop-uvicorn",
            daemon=True,
        )
        self._thread.start()
        self._owns_server = True

        if not wait_for_healthcheck(self.base_url, timeout_seconds=10.0):
            raise RuntimeError(
                f"HumanLoop desktop could not start the local app at {self.base_url}."
            )

    def stop(self) -> None:
        if not self._owns_server or self._server is None or self._thread is None:
            return

        self._server.should_exit = True
        self._thread.join(timeout=5.0)


def set_windows_app_id(app_id: str) -> None:
    if sys.platform != "win32":
        return

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def wait_for_healthcheck(base_url: str, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if fetch_healthcheck(base_url):
            return True
        time.sleep(0.15)
    return False


def fetch_healthcheck(base_url: str) -> bool:
    try:
        payload = _read_json(f"{base_url}{HEALTHCHECK_PATH}")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return False

    return payload.get("status") == "ok"


def fetch_queue_summary(base_url: str) -> QueueSummary | None:
    try:
        payload = _read_json(f"{base_url}{QUEUE_SUMMARY_PATH}")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None

    return QueueSummary.from_payload(payload)


def should_show_queue_toast(
    previous_summary: QueueSummary | None,
    current_summary: QueueSummary,
    *,
    window_active: bool,
) -> bool:
    if previous_summary is None or window_active:
        return False
    if current_summary.pending_count <= 0 or current_summary.latest_pending_seq is None:
        return False

    previous_latest = previous_summary.latest_pending_seq or 0
    return current_summary.latest_pending_seq > previous_latest


def build_queue_toast(summary: QueueSummary) -> tuple[str, str]:
    if summary.pending_count == 1:
        title = "HumanLoop: new prompt ready"
        body = "There is 1 pending prompt waiting in the inbox."
    else:
        title = "HumanLoop: queue updated"
        body = f"There are {summary.pending_count} pending prompts waiting in the inbox."

    if summary.current_prompt_seq is not None and summary.current_prompt_source:
        body = (
            f"{body} Current prompt: Seq {summary.current_prompt_seq} "
            f"from {summary.current_prompt_source}."
        )

    return title, body


def format_window_title(page_title: str | None) -> str:
    cleaned = (page_title or "").strip()
    if not cleaned:
        return DESKTOP_APP_NAME
    return f"{DESKTOP_APP_NAME} - {cleaned}"


def icon_state_for_summary(summary: QueueSummary) -> str:
    return "alert" if summary.pending_count > 0 else "idle"


def should_flash_taskbar(summary: QueueSummary, *, window_active: bool) -> bool:
    return summary.pending_count > 0 and not window_active


def format_tray_tooltip(summary: QueueSummary) -> str:
    if summary.pending_count <= 0:
        return "HumanLoop Desktop: queue empty"

    prompt_label = ""
    if summary.current_prompt_seq is not None:
        prompt_label = f" Current Seq {summary.current_prompt_seq}."

    return f"HumanLoop Desktop: {summary.pending_count} pending.{prompt_label}"


def flash_taskbar(window_handle: int, *, count: int = 5) -> None:
    if sys.platform != "win32" or window_handle <= 0:
        return

    info = FLASHWINFO(
        cbSize=ctypes.sizeof(FLASHWINFO),
        hwnd=window_handle,
        dwFlags=FLASHW_TRAY,
        uCount=count,
        dwTimeout=0,
    )
    ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))


def stop_taskbar_flash(window_handle: int) -> None:
    if sys.platform != "win32" or window_handle <= 0:
        return

    info = FLASHWINFO(
        cbSize=ctypes.sizeof(FLASHWINFO),
        hwnd=window_handle,
        dwFlags=FLASHW_STOP,
        uCount=0,
        dwTimeout=0,
    )
    ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))


def _read_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=2.0) as response:  # noqa: S310 - localhost only
        payload = json.load(response)

    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object response.")
    return payload


def _load_desktop_icon(
    icon_paths: list[Path],
    fallback_path: Path,
    qicon_class,
) -> object:
    icon = qicon_class()
    for path in icon_paths:
        if path.exists():
            icon.addFile(str(path))

    if icon.isNull():
        icon = qicon_class(str(fallback_path))

    return icon


def configure_inbox_webview(webview) -> None:
    try:
        from PySide6.QtWebEngineCore import QWebEngineSettings
    except ImportError as exc:  # pragma: no cover - exercised only with desktop extras
        raise RuntimeError(
            "HumanLoop desktop requires PySide6. Install it with "
            "`.\\.venv\\Scripts\\python.exe -m pip install -e .[desktop]`."
        ) from exc

    # Without explicit clipboard access, the desktop shell can leave the copy
    # button path waiting on navigator.clipboard.writeText(...) indefinitely.
    webview.settings().setAttribute(
        QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
        True,
    )


def run() -> None:
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QAction, QDesktopServices, QIcon
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QSystemTrayIcon
    except ImportError as exc:
        raise RuntimeError(
            "HumanLoop desktop requires PySide6. Install it with "
            "`.\\.venv\\Scripts\\python.exe -m pip install -e .[desktop]`."
        ) from exc

    settings = Settings.from_env()
    server = DesktopServerHandle(settings)
    server.ensure_running()

    set_windows_app_id(DESKTOP_APP_ID)

    app = QApplication(sys.argv)
    app.setApplicationName(DESKTOP_APP_NAME)

    icons = {
        "idle": _load_desktop_icon(IDLE_ICON_PNG_PATHS, IDLE_ICON_PATH, QIcon),
        "alert": _load_desktop_icon(ALERT_ICON_PNG_PATHS, ALERT_ICON_PATH, QIcon),
    }
    app.setWindowIcon(icons["idle"])

    inbox_url = f"{server.base_url}{INBOX_PATH}"
    window = QMainWindow()
    window.setWindowTitle(format_window_title(None))
    window.setWindowIcon(icons["idle"])
    window.resize(1280, 900)

    webview = QWebEngineView(window)
    configure_inbox_webview(webview)
    webview.titleChanged.connect(
        lambda page_title: window.setWindowTitle(format_window_title(page_title))
    )
    webview.setUrl(QUrl(inbox_url))
    window.setCentralWidget(webview)

    tray = QSystemTrayIcon(icons["idle"], window)
    tray.setToolTip("HumanLoop Desktop")
    tray_menu = QMenu()

    show_action = QAction("Show Inbox", tray_menu)
    open_browser_action = QAction("Open In Browser", tray_menu)
    quit_action = QAction("Quit HumanLoop", tray_menu)
    tray_menu.addAction(show_action)
    tray_menu.addAction(open_browser_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)
    tray.setContextMenu(tray_menu)

    def show_window() -> None:
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()

    show_action.triggered.connect(show_window)
    open_browser_action.triggered.connect(
        lambda: QDesktopServices.openUrl(QUrl(inbox_url))
    )
    quit_action.triggered.connect(app.quit)
    tray.activated.connect(lambda *_args: show_window())
    tray.show()

    summary_state: dict[str, QueueSummary | None] = {"last": None}

    def apply_summary_visuals(summary: QueueSummary) -> None:
        state = icon_state_for_summary(summary)
        icon = icons[state]
        app.setWindowIcon(icon)
        window.setWindowIcon(icon)
        tray.setIcon(icon)

    def poll_queue() -> None:
        summary = fetch_queue_summary(server.base_url)
        if summary is None:
            return

        apply_summary_visuals(summary)
        tray.setToolTip(format_tray_tooltip(summary))
        if should_show_queue_toast(
            summary_state["last"],
            summary,
            window_active=window.isActiveWindow(),
        ):
            flash_taskbar(int(window.winId()), count=6)
            if QSystemTrayIcon.supportsMessages():
                title, body = build_queue_toast(summary)
                tray.showMessage(
                    title,
                    body,
                    QSystemTrayIcon.MessageIcon.Information,
                    6000,
                )
        elif should_flash_taskbar(summary, window_active=window.isActiveWindow()):
            flash_taskbar(int(window.winId()), count=3)
        else:
            stop_taskbar_flash(int(window.winId()))

        summary_state["last"] = summary

    poll_timer = QTimer(window)
    poll_timer.setInterval(DESKTOP_POLL_INTERVAL_MS)
    poll_timer.timeout.connect(poll_queue)
    poll_timer.start()

    app.aboutToQuit.connect(tray.hide)
    app.aboutToQuit.connect(server.stop)

    window.show()
    poll_queue()
    raise SystemExit(app.exec())
