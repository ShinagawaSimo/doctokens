"""Slow snapshot I/O must not hold the shared cache lock or duplicate copies."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_core.execution import checkpoint

FIXTURES = Path(__file__).resolve().parents[1] / "test_support/fixtures"


def test_inflight_snapshot_is_reserved_once_and_does_not_block_other_documents() -> None:
    entered, release = threading.Event(), threading.Event()
    source_path = FIXTURES / "docx/docx-paragraph.docx"
    original = Path.open
    copies = []

    class SlowReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.stream.close()

        def read(self, amount):
            entered.set()
            while not release.wait(0.01):
                checkpoint()
            return self.stream.read(amount)

    def slow_open(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        if path == source_path and args and args[0] == "rb":
            copies.append(path)
            return SlowReader(stream)
        return stream

    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        ThreadPoolExecutor(max_workers=2) as workers,
        patch.object(Path, "open", slow_open),
    ):
        try:
            first = workers.submit(runtime.execute, "inspect_document", {"path": str(source_path)})
            assert entered.wait(2)
            second = workers.submit(runtime.execute, "inspect_document", {"path": str(source_path)})
            info = runtime.execute("get_runtime_info", {}).data
            assert info["pending_snapshot_bytes"] == source_path.stat().st_size
            other = runtime.execute("read_xlsx", {"path": "xlsx/xlsx-sparse.xlsx"})
            assert other.error is None
            release.set()
            results = [f.result(timeout=3) for f in (first, second)]
            assert all(result.error is None for result in results)
            assert results[0].data["document_id"] == results[1].data["document_id"]
            assert len(copies) == 1
            assert runtime.execute("get_runtime_info", {}).data["pending_snapshot_bytes"] == 0
        finally:
            release.set()
