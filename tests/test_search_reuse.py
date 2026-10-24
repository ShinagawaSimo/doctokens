"""Bounded search ownership, continuation reuse and eviction on native files."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_excel import XlsxTextSource, find_xlsx_text
from doctokens_excel.parsing.modules.workbook.metadata import _parse_shared_strings
from doctokens_excel.parsing.modules.worksheets.value_rows import iter_value_rows

FIXTURES = Path(__file__).resolve().parents[1] / "test_support/fixtures/xlsx"
SOURCE = "xlsx-shared-strings.xlsx"


def test_three_pages_and_context_changes_share_one_source_and_one_value_scan() -> None:
    from doctokens_core.text_search import TextSearchOptions

    expected = find_xlsx_text(FIXTURES / SOURCE, "text", search_options=TextSearchOptions(limit=200))
    assert len(expected.matches) >= 3
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        patch("doctokens_excel._operation_source._parse_shared_strings", wraps=_parse_shared_strings) as strings,
        patch("doctokens_excel.text_source.iter_value_rows", wraps=iter_value_rows) as scans,
    ):
        gathered = []
        identifier = None
        for offset in (0, 1, 2):
            args = {"document_id": identifier} if identifier else {"path": SOURCE}
            result = runtime.execute("find_document_text", {**args, "query": "text", "limit": 1, "offset": offset})
            assert result.error is None
            identifier = result.data["document_id"]
            gathered.extend(result.data["parts"])
        assert [part["text"] for part in gathered] == [match.text for match in expected.matches[:3]]
        assert [part["selection"] for part in gathered] == [match.locator for match in expected.matches[:3]]
        shorter = runtime.execute(
            "find_document_text",
            {"document_id": identifier, "query": "text", "limit": 1, "context_before": 0, "context_after": 0},
        )
        assert shorter.error is None and len(shorter.data["parts"][0]["text"]) <= len(gathered[0]["text"])
        assert strings.call_count == scans.call_count == 1
        runtime.execute("release_document", {"document_id": identifier})
        assert runtime.execute("get_runtime_info", {}).data["search_estimated_bytes"] == 0


@pytest.mark.parametrize("setting", [{"max_search_bytes": 1}, {"max_search_states": 1}])
def test_evicted_search_can_rebuild_without_changing_source_identity(setting) -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), **setting)) as runtime:
        first = runtime.execute("find_document_text", {"path": SOURCE, "query": "text", "limit": 1})
        identifier = first.data["document_id"]
        runtime.execute("find_document_text", {"document_id": identifier, "query": "1", "limit": 1})
        rebuilt = runtime.execute("find_document_text", {"document_id": identifier, "query": "text", "limit": 1})
        assert rebuilt.error is None and rebuilt.data == first.data
        info = runtime.execute("get_runtime_info", {}).data
        assert info["search_estimated_bytes"] <= runtime.config.max_search_bytes
        assert info["search_states"] <= runtime.config.max_search_states


def test_expiry_closes_source_without_expiring_the_snapshot() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), search_idle_seconds=600)) as runtime:
        first = runtime.execute("find_document_text", {"path": SOURCE, "query": "text", "limit": 1})
        identifier = first.data["document_id"]
        state = next(iter(runtime._searches.entries.values()))
        source = state.source
        assert source is not None
        state.touched = time.monotonic() - 601
        runtime._searches.expire(set(runtime._documents.documents))
        assert source.estimated_memory_bytes == 0
        assert not runtime._searches.entries and runtime._searches.bytes == 0
        assert runtime._documents.documents[identifier].snapshot.is_file()
        assert runtime.execute("release_document", {"document_id": identifier}).data["released"]


def test_resumable_source_requires_explicit_lifetime() -> None:
    source = XlsxTextSource(FIXTURES / SOURCE)
    with pytest.raises(RuntimeError, match="not open"):
        iter(source)
    with source:
        next(iter(source))
        assert source.estimated_memory_bytes > 0
    with pytest.raises(RuntimeError, match="not open"):
        iter(source)
    with pytest.raises(RuntimeError, match="twice"):
        source.__enter__()


def test_cancelled_resume_closes_mutable_state_and_next_request_rebuilds() -> None:
    from doctokens_agent_tools.search_cursor import SearchCursor
    from doctokens_core.execution import ParseControl

    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        first = runtime.execute("find_document_text", {"path": SOURCE, "query": "text", "limit": 1})
        identifier = first.data["document_id"]
        previous = next(iter(runtime._searches.entries.values())).source
        control = ParseControl()
        original = SearchCursor.read

        def cancelled(self, *args):
            control.cancel()
            return original(self, *args)

        args = {"document_id": identifier, "query": "text", "limit": 1, "offset": 1}
        with patch.object(SearchCursor, "read", cancelled):
            result = runtime.execute("find_document_text", args, control=control)
        assert result.error["code"] == "CANCELLED"
        assert previous.estimated_memory_bytes == 0 and not runtime._searches.entries
        assert runtime.execute("find_document_text", args).error is None


def test_full_session_releases_duplicate_search_reader_and_reuses_session_search() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        first = runtime.execute("find_document_text", {"path": SOURCE, "query": "text", "limit": 1})
        identifier = first.data["document_id"]
        assert runtime.execute("get_runtime_info", {}).data["search_states"] == 1
        full = runtime.execute("inspect_document", {"document_id": identifier, "full_parse": True})
        assert full.error is None
        info = runtime.execute("get_runtime_info", {}).data
        assert info["sessions"] == 1 and info["search_states"] == info["search_estimated_bytes"] == 0
        again = runtime.execute("find_document_text", {"document_id": identifier, "query": "text", "offset": 1})
        assert again.error is None
        assert runtime.execute("get_runtime_info", {}).data["search_states"] == 0
