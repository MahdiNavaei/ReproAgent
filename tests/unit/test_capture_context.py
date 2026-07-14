import asyncio
from pathlib import Path

import pytest

from reproagent.agentcase import load_agentcase
from reproagent.capture import NestedCaptureSessionError, capture, get_current_session
from reproagent.domain import EventType


def test_current_session_is_explicit_and_cleared_after_exit() -> None:
    assert get_current_session() is None
    with capture() as session:
        assert get_current_session() is session
    assert get_current_session() is None


def test_nested_top_level_sessions_are_rejected() -> None:
    with capture() as outer:
        assert get_current_session() is outer
        with pytest.raises(NestedCaptureSessionError), capture():
            pass
        assert get_current_session() is outer


def test_sequential_independent_sessions_do_not_leak_events(tmp_path: Path) -> None:
    first_path = tmp_path / "first.agentcase"
    second_path = tmp_path / "second.agentcase"

    with capture(output=first_path) as first:
        first.message(role="user", content="first")
    with capture(output=second_path) as second:
        second.message(role="user", content="second")

    first_case = load_agentcase(first_path)
    second_case = load_agentcase(second_path)
    assert first_case.case_id != second_case.case_id
    assert first_case.events[1].payload["content"] == "first"
    assert second_case.events[1].payload["content"] == "second"


def test_asyncio_tasks_share_context_session_and_keep_contiguous_order(tmp_path: Path) -> None:
    output = tmp_path / "async.agentcase"

    async def run_tasks() -> None:
        async def worker(index: int) -> None:
            await asyncio.sleep(0)
            session = get_current_session()
            assert session is not None
            session.custom(payload={"worker": index})

        await asyncio.gather(*(worker(index) for index in range(20)))

    with capture(output=output):
        asyncio.run(run_tasks())

    case = load_agentcase(output)
    assert [event.sequence for event in case.events] == list(range(len(case.events)))
    custom_events = [event for event in case.events if event.event_type == EventType.CUSTOM]
    assert len(custom_events) == 20
