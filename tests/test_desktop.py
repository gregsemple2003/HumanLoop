from __future__ import annotations

from app.desktop import (
    QueueSummary,
    build_queue_toast,
    format_window_title,
    format_tray_tooltip,
    icon_state_for_summary,
    should_flash_taskbar,
    should_show_queue_toast,
)


def test_queue_summary_from_payload_extracts_current_prompt_fields() -> None:
    summary = QueueSummary.from_payload(
        {
            "pending_count": 2,
            "latest_pending_seq": 9,
            "current_prompt": {
                "id": "prompt-001",
                "seq": 4,
                "source": "capture-alpha",
            },
        }
    )

    assert summary == QueueSummary(
        pending_count=2,
        latest_pending_seq=9,
        current_prompt_id="prompt-001",
        current_prompt_seq=4,
        current_prompt_source="capture-alpha",
    )


def test_should_show_queue_toast_only_when_new_work_arrives_in_background() -> None:
    previous = QueueSummary(
        pending_count=1,
        latest_pending_seq=10,
        current_prompt_id="prompt-001",
        current_prompt_seq=10,
        current_prompt_source="capture-alpha",
    )
    current = QueueSummary(
        pending_count=2,
        latest_pending_seq=11,
        current_prompt_id="prompt-001",
        current_prompt_seq=10,
        current_prompt_source="capture-alpha",
    )

    assert should_show_queue_toast(previous, current, window_active=False) is True
    assert should_show_queue_toast(previous, current, window_active=True) is False
    assert (
        should_show_queue_toast(
            previous,
            QueueSummary(
                pending_count=0,
                latest_pending_seq=None,
                current_prompt_id=None,
                current_prompt_seq=None,
                current_prompt_source=None,
            ),
            window_active=False,
        )
        is False
    )


def test_build_queue_toast_and_tooltip_use_human_readable_copy() -> None:
    summary = QueueSummary(
        pending_count=3,
        latest_pending_seq=15,
        current_prompt_id="prompt-007",
        current_prompt_seq=7,
        current_prompt_source="manual-smoke",
    )

    title, body = build_queue_toast(summary)

    assert title == "HumanLoop: queue updated"
    assert body == (
        "There are 3 pending prompts waiting in the inbox. "
        "Current prompt: Seq 7 from manual-smoke."
    )
    assert format_tray_tooltip(summary) == "HumanLoop Desktop: 3 pending. Current Seq 7."
    assert icon_state_for_summary(summary) == "alert"


def test_format_tray_tooltip_handles_empty_queue() -> None:
    summary = QueueSummary(
        pending_count=0,
        latest_pending_seq=None,
        current_prompt_id=None,
        current_prompt_seq=None,
        current_prompt_source=None,
    )

    assert format_tray_tooltip(summary) == "HumanLoop Desktop: queue empty"
    assert icon_state_for_summary(summary) == "idle"


def test_format_window_title_prefixes_desktop_shell_identity() -> None:
    assert format_window_title(None) == "HumanLoop Desktop"
    assert (
        format_window_title("HumanLoop Inbox (1 pending)")
        == "HumanLoop Desktop - HumanLoop Inbox (1 pending)"
    )


def test_should_flash_taskbar_tracks_pending_work_while_unfocused() -> None:
    pending = QueueSummary(
        pending_count=1,
        latest_pending_seq=3,
        current_prompt_id="prompt-003",
        current_prompt_seq=3,
        current_prompt_source="manual-smoke",
    )
    empty = QueueSummary(
        pending_count=0,
        latest_pending_seq=None,
        current_prompt_id=None,
        current_prompt_seq=None,
        current_prompt_source=None,
    )

    assert should_flash_taskbar(pending, window_active=False) is True
    assert should_flash_taskbar(pending, window_active=True) is False
    assert should_flash_taskbar(empty, window_active=False) is False
