"""Cancellation and ownership races with native inputs and controlled blocking."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_agent_tools.models import ToolResponse
from ooxml_llm_core.execution import ParseCancelled, ParseControl, checkpoint, parse_scope

FIXTURES = Path(__file__).resolve().parents[1] / "test_support/fixtures"


def _idle(runtime: ToolRuntime) -> bool:
    with runtime._condition:
        return runtime._condition.wait_for(lambda: not runtime._active, timeout=2)


def test_busy_document_does_not_block_status_or_another_document_and_cancel_preserves_completed_data() -> None:
    entered, finished = threading.Event(), threading.Event()

    async def verify() -> None:
        with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), workers=2)) as runtime:
            first = runtime.execute("inspect_document", {"path": "docx/docx-paragraph.docx"})
            identifier = first.data["document_id"]
            document = runtime._documents.documents[identifier]
            previous = document.session
            saved = runtime._results.put(identifier, "previous completed result", {})
            original = runtime._operations.run

            def blocked(name, current, args):
                if current.id == identifier:
                    entered.set()
                    try:
                        while not finished.wait(0.01):
                            checkpoint("controlled slow operation")
                    finally:
                        finished.set()
                return original(name, current, args)

            with patch.object(runtime._operations, "run", side_effect=blocked):
                task = asyncio.create_task(runtime.aexecute("read_docx", {"document_id": identifier}))
                assert await asyncio.to_thread(entered.wait, 2)
                info = await asyncio.wait_for(runtime.aexecute("get_runtime_info", {}), 1)
                assert info.error is None
                released = await asyncio.wait_for(runtime.aexecute("release_document", {"document_id": identifier}), 1)
                assert released.error["code"] == "DOCUMENT_BUSY"
                other = await asyncio.wait_for(runtime.aexecute("read_xlsx", {"path": "xlsx/xlsx-sparse.xlsx"}), 2)
                assert other.error is None
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert await asyncio.to_thread(finished.wait, 2)
                assert await asyncio.to_thread(_idle, runtime)
            assert document.session is previous
            assert runtime.execute("read_result", {"result_id": saved.id}).data["text"] == "previous completed result"
            assert runtime.execute("release_document", {"document_id": identifier}).data["released"]

    try:
        asyncio.run(verify())
    finally:
        finished.set()


def test_status_bypasses_saturated_parser_workers() -> None:
    entered = [threading.Event(), threading.Event()]
    leave = threading.Event()

    async def verify() -> None:
        with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), workers=2)) as runtime:

            def blocked(_name, document, _args):
                entered[0 if document.format == "docx" else 1].set()
                while not leave.wait(0.01):
                    checkpoint()
                return ToolResponse({"document_id": document.id})

            with patch.object(runtime._operations, "run", side_effect=blocked):
                tasks = [
                    asyncio.create_task(runtime.aexecute(name, {"path": path}))
                    for name, path in (("read_docx", "docx/docx-paragraph.docx"), ("read_xlsx", "xlsx/xlsx-sparse.xlsx"))
                ]
                assert all(await asyncio.gather(*(asyncio.to_thread(event.wait, 2) for event in entered)))
                assert (await asyncio.wait_for(runtime.aexecute("get_runtime_info", {}), 1)).error is None
                leave.set()
                assert all(result.error is None for result in await asyncio.gather(*tasks))

    try:
        asyncio.run(verify())
    finally:
        leave.set()


def test_native_parse_cancellation_discards_partial_session_and_reservation() -> None:
    from xlsx_llm_parser.parsing.modules.worksheets.scanner import WorksheetScanner

    context = ParseControl()
    original = WorksheetScanner._read_row

    def cancel_after_row(self, *args):
        original(self, *args)
        context.cancel()

    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        with patch.object(WorksheetScanner, "_read_row", cancel_after_row):
            result = runtime.execute("inspect_document", {"path": "xlsx/xlsx-sparse.xlsx", "full_parse": True}, control=context)
        assert result.error["code"] == "CANCELLED"
        document = next(iter(runtime._documents.documents.values()))
        assert document.session is None and not document.session_loading
        assert document.session_memory_bytes == 0 and document.active == 0
        assert document.snapshot.is_file()
        assert runtime.execute("read_xlsx", {"document_id": document.id}).error is None


def test_same_snapshot_full_parse_is_established_once() -> None:
    from doctokens_agent_tools.sessions import _open

    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        ThreadPoolExecutor(max_workers=2) as workers,
        patch("doctokens_agent_tools.sessions._open", wraps=_open) as opened,
    ):
        futures = [
            workers.submit(runtime.execute, "inspect_document", {"path": "docx/docx-paragraph.docx", "full_parse": True})
            for _ in range(2)
        ]
        results = [f.result(timeout=3) for f in futures]
        assert all(result.error is None for result in results)
        assert results[0].data["document_id"] == results[1].data["document_id"]
        assert opened.call_count == 1


def test_cancelled_result_admission_rolls_back_eviction() -> None:
    from doctokens_agent_tools.results import ResultStore

    store = ResultStore(RuntimeConfig(allowed_roots=(FIXTURES,), max_result_bytes=700))
    old = store.put("document", "old result", {})
    control = ParseControl()
    with pytest.raises(ParseCancelled), parse_scope(control), store.transaction():
        store.put("document", "x" * 400, {})
        control.cancel()
    assert list(store.entries) == [old.id]
    assert store.bytes == old.size and not store.operations


def test_closed_async_runtime_returns_a_stable_error() -> None:
    runtime = ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,)))
    runtime.close()
    result = asyncio.run(runtime.aexecute("read_xlsx", {"path": "xlsx/xlsx-sparse.xlsx"}))
    assert result.error["code"] == "RUNTIME_CLOSED"


def test_concurrent_loading_sessions_reserve_growth_before_parsing() -> None:
    from doctokens_agent_tools.sessions import _open

    mib = 1024 * 1024
    entered = [threading.Event(), threading.Event()]
    release = threading.Event()
    allowances = []

    def slower(document, allowance):
        session = _open(document, allowance)
        original = session.__enter__

        def begin():
            entered[0 if document.format == "docx" else 1].set()
            while not release.wait(0.01):
                checkpoint()
            return original()

        session.__enter__ = begin
        allowances.append(allowance)
        return session

    with (
        ToolRuntime(
            RuntimeConfig(allowed_roots=(FIXTURES,), max_session_memory_bytes=6 * mib, max_session_total_memory_bytes=10 * mib)
        ) as runtime,
        ThreadPoolExecutor(max_workers=2) as workers,
        patch("doctokens_agent_tools.sessions._open", side_effect=slower),
    ):
        try:
            futures = [
                workers.submit(runtime.execute, "inspect_document", {"path": path, "full_parse": True})
                for path in ("docx/docx-paragraph.docx", "xlsx/xlsx-sparse.xlsx")
            ]
            assert all(event.wait(2) for event in entered)
            info = runtime.execute("get_runtime_info", {}).data
            assert info["loading_sessions"] == 2 and info["session_estimated_bytes"] == 10 * mib
            assert sorted(allowances) == [4 * mib, 6 * mib]
            release.set()
            assert all(f.result(timeout=3).error is None for f in futures)
            assert runtime.execute("get_runtime_info", {}).data["session_estimated_bytes"] <= 10 * mib
        finally:
            release.set()
