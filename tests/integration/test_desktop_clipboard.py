from __future__ import annotations

import json
import time

import httpx
import pytest

pytest.importorskip("PySide6.QtWebEngineWidgets")

from PySide6.QtCore import QEventLoop, QPoint, Qt, QTimer, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

from app.desktop import configure_inbox_webview


def _enqueue_prompt(client: httpx.Client, suffix: str, *, body: str) -> dict:
    response = client.post(
        "/api/prompts",
        json={
            "body": body,
            "source": "desktop-clipboard-tests",
            "idempotency_key": f"desktop-clipboard-{suffix}",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _wait(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _run_js(page, script: str, *, timeout_ms: int = 5000):
    loop = QEventLoop()
    box: dict[str, object] = {}

    def done(value) -> None:
        box["value"] = value
        loop.quit()

    page.runJavaScript(script, done)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return box.get("value")


def _load_inbox(view: QWebEngineView, base_url: str) -> None:
    load_loop = QEventLoop()
    view.page().loadFinished.connect(lambda _ok: load_loop.quit())
    view.setUrl(QUrl(f"{base_url}/inbox"))
    view.show()
    QTimer.singleShot(10000, load_loop.quit)
    load_loop.exec()
    _wait(800)


def _click_copy_button(view: QWebEngineView) -> None:
    _click_button(view, "copy-prompt-button")


def _click_button(view: QWebEngineView, element_id: str) -> None:
    rect_json = _run_js(
        view.page(),
        f"""
        JSON.stringify((() => {{
            const rect = document.getElementById("{element_id}").getBoundingClientRect();
            return {{
                x: rect.left + rect.width / 2,
                y: rect.top + rect.height / 2,
            }};
        }})())
        """,
    )
    rect = json.loads(rect_json)
    target = view.focusProxy() or view
    target.setFocus()
    view.activateWindow()
    _wait(500)
    QTest.mouseClick(
        target,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(rect["x"]), int(rect["y"])),
    )


def _read_copy_state(view: QWebEngineView) -> dict[str, object]:
    state_json = _run_js(
        view.page(),
        """
        JSON.stringify({
            ariaBusy: document.getElementById("current-prompt")?.getAttribute("aria-busy"),
            indicatorHidden: document.getElementById("prompt-action-indicator")?.hidden,
            statusKind: document.getElementById("workflow-status")?.dataset.kind,
            statusTitle: document.getElementById("workflow-status-title")?.textContent,
            statusDetail: document.getElementById("workflow-status-detail")?.textContent,
            copyCount: document.getElementById("current-copy-count")?.textContent,
        })
        """,
    )
    return json.loads(state_json)


def _focus_webview(view: QWebEngineView):
    target = view.focusProxy() or view
    target.setFocus()
    view.activateWindow()
    _wait(500)
    return target


def _press_key(
    view: QWebEngineView,
    key: Qt.Key,
    modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    target = _focus_webview(view)
    QTest.keyClick(target, key, modifier)


def _read_inbox_state(view: QWebEngineView) -> dict[str, object]:
    state_json = _run_js(
        view.page(),
        """
        JSON.stringify({
            activeElementId: document.activeElement?.id ?? "",
            ariaBusy: document.getElementById("current-prompt")?.getAttribute("aria-busy"),
            currentPromptId: document.getElementById("current-prompt")?.dataset.promptId ?? "",
            currentPromptBody: document.getElementById("current-prompt-body")?.textContent ?? "",
            copyCount: document.getElementById("current-copy-count")?.textContent ?? "",
            indicatorHidden: document.getElementById("prompt-action-indicator")?.hidden,
            queueCount: document.getElementById("queue-rail")?.dataset.queueCount ?? "",
            waitingCount: document.getElementById("queue-rail")?.dataset.waitingCount ?? "",
            queueText: document.getElementById("queue-rail")?.textContent ?? "",
            requeueHidden: document.getElementById("requeue-dismissed-button")?.hidden,
            requeueLabel: document.getElementById("requeue-dismissed-button")?.textContent ?? "",
            requeuePromptId: document.getElementById("requeue-dismissed-button")?.dataset.promptId ?? "",
            shortcutHelpExpanded: document.getElementById("shortcut-help-toggle")?.getAttribute("aria-expanded") ?? "",
            shortcutHelpHidden: document.getElementById("shortcut-help")?.hidden,
            statusDetail: document.getElementById("workflow-status-detail")?.textContent ?? "",
            statusKind: document.getElementById("workflow-status")?.dataset.kind ?? "",
            statusTitle: document.getElementById("workflow-status-title")?.textContent ?? "",
            title: document.title,
        })
        """,
    )
    return json.loads(state_json)


def _wait_for_inbox_state(
    view: QWebEngineView,
    predicate,
    *,
    timeout_ms: int = 5000,
    description: str,
) -> dict[str, object]:
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    last_state: dict[str, object] | None = None

    while time.monotonic() < deadline:
        last_state = _read_inbox_state(view)
        if predicate(last_state):
            return last_state
        _wait(100)

    pytest.fail(f"Timed out waiting for {description}. Last state: {last_state!r}")


def test_raw_qwebengine_mouse_copy_reproduces_the_busy_hang(
    live_server,
    qt_app,
) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        _enqueue_prompt(client, "raw-mouse", body="Mouse copy repro prompt")

        view = QWebEngineView()
        try:
            view.resize(1280, 900)
            _load_inbox(view, live_server.base_url)
            _click_copy_button(view)
            _wait(2000)

            state = _read_copy_state(view)
            next_prompt = client.get("/api/prompts/next").json()
        finally:
            view.close()

    assert state["ariaBusy"] == "true"
    assert state["indicatorHidden"] is False
    assert state["statusKind"] == "info"
    assert state["statusTitle"] == "Manual handoff is ready."
    assert state["copyCount"] == "0"
    assert next_prompt["copy_count"] == 0


def test_configured_desktop_webview_mouse_copy_resolves_cleanly(
    live_server,
    qt_app,
) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        _enqueue_prompt(client, "configured-mouse", body="Mouse copy fixed prompt")

        view = QWebEngineView()
        try:
            view.resize(1280, 900)
            configure_inbox_webview(view)
            _load_inbox(view, live_server.base_url)
            _click_copy_button(view)
            _wait(2000)

            state = _read_copy_state(view)
            next_prompt = client.get("/api/prompts/next").json()
        finally:
            view.close()

    assert state["ariaBusy"] == "false"
    assert state["indicatorHidden"] is True
    assert state["statusKind"] == "success"
    assert state["statusTitle"] == "Copied"
    assert state["copyCount"] == "1"
    assert next_prompt["copy_count"] == 1


def test_configured_desktop_keyboard_loop_copies_and_completes_without_losing_place(
    live_server,
    qt_app,
) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        first = _enqueue_prompt(
            client,
            "keyboard-current",
            body="Keyboard current prompt body",
        )
        second = _enqueue_prompt(
            client,
            "keyboard-next",
            body="Keyboard next prompt body",
        )

        view = QWebEngineView()
        try:
            view.resize(1280, 900)
            configure_inbox_webview(view)
            _load_inbox(view, live_server.base_url)

            initial_state = _read_inbox_state(view)

            _press_key(
                view,
                Qt.Key.Key_Slash,
                Qt.KeyboardModifier.ShiftModifier,
            )
            help_state = _wait_for_inbox_state(
                view,
                lambda state: state["shortcutHelpHidden"] is False,
                description="shortcut help to open",
            )

            _press_key(view, Qt.Key.Key_C)
            copied_state = _wait_for_inbox_state(
                view,
                lambda state: (
                    state["statusTitle"] == "Copied"
                    and state["statusKind"] == "success"
                    and state["indicatorHidden"] is True
                    and state["copyCount"] == "1"
                ),
                description="keyboard copy to resolve",
            )
            next_after_copy = client.get("/api/prompts/next").json()

            _press_key(view, Qt.Key.Key_Return)
            completed_state = _wait_for_inbox_state(
                view,
                lambda state: (
                    state["statusTitle"] == "Completed"
                    and state["currentPromptId"] == second["id"]
                    and state["currentPromptBody"] == "Keyboard next prompt body"
                ),
                description="keyboard complete to advance the queue",
            )
            next_after_complete = client.get("/api/prompts/next").json()
        finally:
            view.close()

    assert initial_state["currentPromptId"] == first["id"]
    assert initial_state["currentPromptBody"] == "Keyboard current prompt body"
    assert initial_state["queueCount"] == "2"
    assert initial_state["waitingCount"] == "1"
    assert initial_state["statusTitle"] == "Manual handoff is ready."

    assert help_state["shortcutHelpExpanded"] == "true"

    assert copied_state["currentPromptId"] == first["id"]
    assert copied_state["currentPromptBody"] == "Keyboard current prompt body"
    assert copied_state["queueCount"] == "2"
    assert copied_state["waitingCount"] == "1"
    assert "stayed visible" in copied_state["statusDetail"]
    assert next_after_copy["id"] == first["id"]
    assert next_after_copy["copy_count"] == 1

    assert completed_state["queueCount"] == "1"
    assert completed_state["waitingCount"] == "0"
    assert "server confirmed the change" in completed_state["statusDetail"]
    assert next_after_complete["id"] == second["id"]
    assert next_after_complete["copy_count"] == 0


def test_configured_desktop_queue_polling_keeps_current_sticky_until_dismiss_and_requeue(
    live_server,
    qt_app,
) -> None:
    with httpx.Client(base_url=live_server.base_url, timeout=5.0) as client:
        first = _enqueue_prompt(
            client,
            "polling-current",
            body="Sticky current prompt body",
        )

        view = QWebEngineView()
        try:
            view.resize(1280, 900)
            configure_inbox_webview(view)
            _load_inbox(view, live_server.base_url)

            initial_state = _read_inbox_state(view)

            second = _enqueue_prompt(
                client,
                "polling-next",
                body="Queued while the operator is reading",
            )

            refreshed_state = _wait_for_inbox_state(
                view,
                lambda state: (
                    state["queueCount"] == "2"
                    and state["waitingCount"] == "1"
                    and "Queued while the operator is reading" in state["queueText"]
                ),
                timeout_ms=12000,
                description="queue rail polling refresh after a new prompt arrives",
            )

            _press_key(view, Qt.Key.Key_D)
            dismissed_state = _wait_for_inbox_state(
                view,
                lambda state: (
                    state["statusTitle"] == "Dismissed"
                    and state["currentPromptId"] == second["id"]
                    and state["currentPromptBody"] == "Queued while the operator is reading"
                    and state["requeueHidden"] is False
                ),
                description="dismiss action to expose the requeue recovery path",
            )
            next_after_dismiss = client.get("/api/prompts/next").json()

            _click_button(view, "requeue-dismissed-button")
            requeued_state = _wait_for_inbox_state(
                view,
                lambda state: (
                    state["statusTitle"] == "Requeued"
                    and state["currentPromptId"] == first["id"]
                    and state["currentPromptBody"] == "Sticky current prompt body"
                    and state["requeueHidden"] is True
                ),
                description="requeue action to restore the original current prompt",
            )
            next_after_requeue = client.get("/api/prompts/next").json()
        finally:
            view.close()

    assert initial_state["currentPromptId"] == first["id"]
    assert initial_state["currentPromptBody"] == "Sticky current prompt body"
    assert initial_state["queueCount"] == "1"
    assert initial_state["waitingCount"] == "0"

    assert refreshed_state["currentPromptId"] == first["id"]
    assert refreshed_state["currentPromptBody"] == "Sticky current prompt body"
    assert refreshed_state["title"] == "HumanLoop Inbox (2 pending)"

    assert dismissed_state["requeuePromptId"] == first["id"]
    assert "Requeue prompt" in dismissed_state["requeueLabel"]
    assert "Use Requeue if you want to restore it." in dismissed_state["statusDetail"]
    assert next_after_dismiss["id"] == second["id"]

    assert requeued_state["queueCount"] == "2"
    assert requeued_state["waitingCount"] == "1"
    assert "Queued while the operator is reading" in requeued_state["queueText"]
    assert next_after_requeue["id"] == first["id"]
