"""Admission, growth rejection and ownership, using native Office inputs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_agent_tools.schemas import SourceArgs
from ooxml_llm_core.limits import PackageLimits
from ooxml_llm_core.memory import ParseMemoryLimitError, SessionMemoryBudget, estimate_session_bytes
from ooxml_llm_core.package import PackageReader
from xlsx_llm_parser import open_xlsx

FIXTURES = Path(__file__).resolve().parents[1] / "test_support/fixtures"
PATHS = ["docx/docx-paragraph.docx", "xlsx/xlsx-sparse.xlsx"]


def _estimate(path: str) -> int:
    with PackageReader(FIXTURES / path, PackageLimits()) as package:
        return estimate_session_bytes(package.read_entry_index())


@pytest.mark.parametrize("name", ["max_session_memory_bytes", "max_session_total_memory_bytes"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_host_memory_limits_are_positive_integers(name, value) -> None:
    with pytest.raises(ValueError, match=name):
        RuntimeConfig(allowed_roots=(FIXTURES,), **{name: value})


def test_existing_positional_host_configuration_keeps_its_argument_order() -> None:
    config = RuntimeConfig((FIXTURES,), 3, 20, 60)
    assert (config.max_sessions, config.max_documents, config.idle_seconds) == (3, 20, 60)
    assert config.max_session_memory_bytes == 256 * 1024 * 1024


@pytest.mark.parametrize("path", PATHS)
def test_rejected_admission_never_opens_a_session_and_preserves_snapshot(path: str) -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), max_session_memory_bytes=1)) as runtime:
        with patch("doctokens_agent_tools.sessions._open", side_effect=AssertionError("should reject before parse")):
            result = runtime.execute("inspect_document", {"path": path, "full_parse": True})
        assert result.error["code"] == "SESSION_MEMORY_LIMIT"
        info = runtime.execute("get_runtime_info", {}).data
        assert info["sessions"] == info["session_estimated_bytes"] == 0
        assert info["documents"] == 1
        document = next(iter(runtime._documents.documents.values()))
        assert document.session is None and document.snapshot.is_file()
        assert runtime.execute("release_document", {"document_id": document.id}).data["released"]
        assert not document.snapshot.exists()


def test_total_budget_evicts_idle_session_but_keeps_result_and_snapshot() -> None:
    total = max(map(_estimate, PATHS)) + 4096
    config = RuntimeConfig(allowed_roots=(FIXTURES,), max_session_total_memory_bytes=total, max_sessions=4)
    with ToolRuntime(config) as runtime:
        first = runtime.execute("inspect_document", {"path": PATHS[0], "full_parse": True})
        assert first.error is None
        doc1 = runtime._documents.documents[first.data["document_id"]]
        previous = doc1.session
        cached = runtime._results.put(doc1.id, "retained result", {})
        second = runtime.execute("inspect_document", {"path": PATHS[1], "full_parse": True})
        assert second.error is None
        assert doc1.session is None and doc1.session_memory_bytes == 0
        with pytest.raises(RuntimeError, match="not open"):
            previous.describe()
        assert runtime.execute("read_result", {"result_id": cached.id}).data["text"] == "retained result"
        assert doc1.snapshot.is_file()
        assert runtime.execute("get_runtime_info", {}).data["session_estimated_bytes"] <= total
        assert runtime.execute("inspect_document", {"document_id": doc1.id, "full_parse": True}).error is None
        for identifier in list(runtime._documents.documents):
            runtime.execute("release_document", {"document_id": identifier})
        assert runtime.execute("get_runtime_info", {}).data["session_estimated_bytes"] == 0


def test_active_session_is_protected_and_cannot_be_overcommitted() -> None:
    total = max(map(_estimate, PATHS)) + 4096
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), max_session_total_memory_bytes=total)) as runtime:
        with runtime._documents.acquire(SourceArgs(path=PATHS[0])) as active:
            runtime._documents.session(active)
            response = runtime.execute("inspect_document", {"path": PATHS[1], "full_parse": True})
            assert response.error["code"] == "SESSION_MEMORY_LIMIT"
            assert active.session is not None
        assert runtime.execute("inspect_document", {"path": PATHS[1], "full_parse": True}).error is None


def test_growth_rejection_closes_parser_and_does_not_commit_partial_session() -> None:
    # Deliberately underestimate admission to exercise in-parse growth using an
    # ordinary native file. This simulates an imperfect heuristic, not Office content.
    with (
        patch("ooxml_llm_core.memory.estimate_session_bytes", return_value=1024),
        patch("doctokens_agent_tools.sessions.estimate_session_bytes", return_value=1024),
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), max_session_memory_bytes=1024 * 1024 + 128)) as runtime,
    ):
        result = runtime.execute("inspect_document", {"path": PATHS[1], "full_parse": True})
        assert result.error["code"] == "SESSION_MEMORY_LIMIT"
        document = next(iter(runtime._documents.documents.values()))
        assert document.session is None and document.session_memory_bytes == 0
        assert runtime.execute("read_xlsx", {"document_id": document.id}).error is None
    with patch("ooxml_llm_core.memory.estimate_session_bytes", return_value=1024):
        session = open_xlsx(FIXTURES / PATHS[1], memory_limit_bytes=1024 * 1024 + 128)
        with pytest.raises(ParseMemoryLimitError):
            session.__enter__()
        assert session.parsed_workbook is None and session._package is None
        session.close()


def test_concurrent_full_session_admissions_share_one_total_budget() -> None:
    total = max(map(_estimate, PATHS)) + 4096
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), max_session_total_memory_bytes=total)) as runtime,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        futures = [pool.submit(runtime.execute, "inspect_document", {"path": path, "full_parse": True}) for path in PATHS]
        results = [f.result() for f in futures]
        assert any(result.error is None for result in results)
        assert all(result.error is None or result.error["code"] == "SESSION_MEMORY_LIMIT" for result in results)
        # A concurrent active owner cannot be evicted. Once it finishes, a
        # rejected request can retry against the same immutable source.
        for path, result in zip(PATHS, results, strict=True):
            if result.error is not None:
                assert runtime.execute("inspect_document", {"path": path, "full_parse": True}).error is None
        info = runtime.execute("get_runtime_info", {}).data
        assert info["sessions"] == 1 and info["session_estimated_bytes"] <= total


def test_fragment_measurement_counts_local_shared_references_once() -> None:
    # Infrastructure identity accounting: this does not define parsing content.
    from ooxml_llm_core.memory import object_bytes

    value = "a" * 1000
    assert object_bytes([value, value]) < object_bytes([value, value.encode().decode()])
    budget = SessionMemoryBudget(1024 * 1024 + 100)
    with pytest.raises(ParseMemoryLimitError):
        budget.add_fragment(value)


def test_growth_reclaims_remaining_idle_owners_before_a_single_retry() -> None:
    # Mock only parser allocation/admission, keeping native snapshot ownership.
    mib = 1024 * 1024
    attempts = []

    def opened(document, allowance):
        needed = 10 * mib if document.format == "docx" else 18 * mib
        session = MagicMock()
        session.estimated_memory_bytes = needed
        session.describe.return_value = {"navigation": {}, "report": {}}
        if allowance < needed:
            session.__enter__.side_effect = ParseMemoryLimitError("simulated growth")
        attempts.append((session, allowance))
        return session

    with (
        ToolRuntime(
            RuntimeConfig(allowed_roots=(FIXTURES,), max_session_memory_bytes=20 * mib, max_session_total_memory_bytes=25 * mib)
        ) as runtime,
        patch("doctokens_agent_tools.sessions._reservation", return_value=10 * mib),
        patch("doctokens_agent_tools.sessions._open", side_effect=opened),
    ):
        assert runtime.execute("inspect_document", {"path": PATHS[0], "full_parse": True}).error is None
        assert runtime.execute("inspect_document", {"path": PATHS[1], "full_parse": True}).error is None
        assert [allowance for _, allowance in attempts] == [20 * mib, 15 * mib, 20 * mib]
        attempts[0][0].close.assert_called_once()
        attempts[1][0].close.assert_called_once()
        assert runtime.execute("get_runtime_info", {}).data["session_estimated_bytes"] == 18 * mib


def test_count_eviction_uses_session_access_order() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), max_sessions=2)) as runtime:
        first = runtime.execute("inspect_document", {"path": PATHS[0], "full_parse": True}).data["document_id"]
        second = runtime.execute("inspect_document", {"path": PATHS[1], "full_parse": True}).data["document_id"]
        runtime.execute("inspect_document", {"document_id": first, "full_parse": True})
        assert runtime.execute("inspect_document", {"path": "xlsx/xlsx-empty.xlsx", "full_parse": True}).error is None
        assert runtime._documents.documents[first].session is not None
        assert runtime._documents.documents[second].session is None
        assert runtime._documents.documents[second].session_memory_bytes == 0
