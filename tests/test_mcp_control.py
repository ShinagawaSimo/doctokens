"""Official SDK progress opt-in and protocol cancellation stop native workers."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_core.execution import checkpoint

pytest.importorskip("mcp")
from doctokens_agent_tools.mcp import build_server
from mcp import types
from mcp.server.session import ServerSession
from mcp.shared.memory import create_connected_server_and_client_session

FIXTURES = Path(__file__).resolve().parents[1] / "test_support/fixtures"


@pytest.mark.parametrize("requested", [False, True])
def test_progress_is_throttled_and_never_enters_document_content(requested: bool) -> None:
    notifications = []
    observed = []
    original_send = ServerSession.send_progress_notification
    wait = threading.Event()

    async def tracked(self, *args, **kwargs):
        notifications.append((args, kwargs))
        await original_send(self, *args, **kwargs)

    async def progress(value, total, message):
        observed.append((value, total, message))

    async def verify() -> None:
        with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
            original = runtime._operations.run

            def slower(*args):
                for _ in range(8):
                    checkpoint("controlled parser stage")
                    wait.wait(0.04)
                return original(*args)

            with (
                patch.object(runtime._operations, "run", side_effect=slower),
                patch.object(ServerSession, "send_progress_notification", tracked),
            ):
                async with create_connected_server_and_client_session(build_server(runtime)) as client:
                    result = await client.call_tool(
                        "read_xlsx", {"path": "xlsx/xlsx-sparse.xlsx"}, progress_callback=progress if requested else None
                    )
                    assert not result.isError
                    assert "controlled parser stage" not in str(result.content)

    asyncio.run(verify())
    if requested:
        assert 1 <= len(observed) == len(notifications) <= 3
        assert [item[0] for item in observed] == sorted({item[0] for item in observed})
        assert all(item[1] is None for item in observed)
    else:
        assert not notifications and not observed


def test_cancel_notification_stops_worker_and_preserves_snapshot() -> None:
    entered, exited = threading.Event(), threading.Event()
    request_id = []

    async def verify() -> None:
        with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
            server = build_server(runtime)
            original = runtime.aexecute

            async def capture(*args, **kwargs):
                request_id.append(server.request_context.request_id)
                return await original(*args, **kwargs)

            def blocked(*_args):
                entered.set()
                try:
                    while not exited.wait(0.01):
                        checkpoint("waiting for cancellation")
                finally:
                    exited.set()

            with (
                patch.object(runtime, "aexecute", side_effect=capture),
                patch.object(runtime._operations, "run", side_effect=blocked),
            ):
                async with create_connected_server_and_client_session(server) as client:
                    task = asyncio.create_task(client.call_tool("read_xlsx", {"path": "xlsx/xlsx-sparse.xlsx"}))
                    assert await asyncio.to_thread(entered.wait, 2)
                    await client.send_notification(
                        types.ClientNotification(
                            types.CancelledNotification(params=types.CancelledNotificationParams(requestId=request_id[0]))
                        )
                    )
                    with pytest.raises(Exception, match="cancelled"):
                        await asyncio.wait_for(task, 2)
                    assert await asyncio.to_thread(exited.wait, 2)

                    def idle():
                        with runtime._condition:
                            return runtime._condition.wait_for(lambda: not runtime._active, timeout=2)

                    assert await asyncio.to_thread(idle)
            document = next(iter(runtime._documents.documents.values()))
            assert document.snapshot.is_file() and document.session is None
            assert runtime.execute("release_document", {"document_id": document.id}).data["released"]

    try:
        asyncio.run(verify())
    finally:
        exited.set()
