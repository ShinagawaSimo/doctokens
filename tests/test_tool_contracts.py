"""Discoverability, host budgets and snapshot lifecycle, using native valid files."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_agent_tools.presentation import Presenter
from doctokens_agent_tools.results import ResultStore

FIXTURES = Path(__file__).resolve().parents[1] / "test_support/fixtures"


def _tools(runtime: ToolRuntime):
    return {tool.name: tool for tool in runtime.list_tools()}


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("read_docx", {}),
        ("read_docx", {"path": "a.docx", "document_id": "id"}),
        ("read_docx", {"document_id": "id", "options": {"include_runs": False}}),
        ("read_xlsx", {"path": "a.xlsx", "options": {"include_raw_hints": True}}),
        ("read_pptx", {"path": "a.pptx", "options": {"locale": "en-US"}}),
        ("read_xlsx", {"path": "a.xlsx", "range_spec": "A1"}),
        ("query_xlsx_data", {"path": "a.xlsx", "sheet": "Data", "range_spec": "A1:C3"}),
        ("query_xlsx_data", {"path": "a.xlsx", "table_id": ""}),
        ("read_result", {"result_id": "id", "length": 101}),
    ],
)
def test_discovery_and_runtime_reject_invalid_combinations(tool: str, arguments: dict) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), max_chunk_size=100)) as runtime:
        schema = _tools(runtime)[tool].input_schema
        assert list(jsonschema.Draft202012Validator(schema).iter_errors(arguments))
        response = runtime.execute(tool, arguments)
        assert response.error is not None and response.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("read_docx", {"path": "a.docx", "document_id": None, "options": {"include_raw_hints": True}}),
        ("read_pptx", {"path": None, "document_id": "id", "options": {}}),
        ("read_xlsx", {"path": "a.xlsx", "sheet": "Data", "range_spec": "A1"}),
        ("query_xlsx_data", {"path": "a.xlsx", "sheet": "Data", "range_spec": "A1:C3", "header_row": 1}),
        ("query_xlsx_data", {"document_id": "id", "table_id": "table1"}),
        ("read_result", {"result_id": "id", "length": None}),
    ],
)
def test_discovery_accepts_supported_combinations(tool: str, arguments: dict) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        schema = _tools(runtime)[tool].input_schema
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(arguments, schema)


def test_general_and_specific_options_share_one_snapshot() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        first = runtime.execute("inspect_document", {"path": "xlsx/xlsx-empty.xlsx", "options": {"locale": "en-US"}})
        second = runtime.execute("read_xlsx", {"path": "xlsx/xlsx-empty.xlsx", "options": {"locale": "en-US"}})
        assert first.error is None and second.error is None
        assert first.data["document_id"] == second.data["document_id"]
        info = runtime.execute("get_runtime_info", {})
        assert info.error is None and info.data["documents"] == 1
        identifier = first.data["document_id"]
        assert runtime.execute("release_document", {"document_id": identifier}).data["released"]
        assert runtime.execute("read_xlsx", {"document_id": identifier}).error["code"] == "DOCUMENT_EXPIRED"
        assert runtime.execute("get_runtime_info", {}).data["snapshot_bytes"] == 0


def test_custom_chunk_defaults_and_base64_budget_match_discovery() -> None:
    config = RuntimeConfig(allowed_roots=(FIXTURES,), reply_chars=9, max_chunk_size=5, result_chunk_chars=100)
    store = ResultStore(config)
    presenter = Presenter(config, store)
    with ToolRuntime(config) as runtime:
        limits = _tools(runtime)["read_result"].input_schema["x-doctokens-result-limits"]
        assert limits == runtime.execute("get_runtime_info", {}).data["result_limits"]
    text = store.put("document", "abcdefghijk", {})
    assert presenter.fragment(text.id, 0, None).data["text"] == "abcde"
    binary = store.put("document", b"abcdefghijk", {})
    assert len(presenter.fragment(binary.id, 0, None).data["data"]) <= config.reply_chars
    assert presenter.fragment(binary.id, 0, None).data["length"] == limits["effective_binary_bytes"]
    assert presenter.fragment(text.id, len(text.value), None).data["next_offset"] is None


def test_bad_options_do_not_echo_input_values_or_allocate_snapshots() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        response = runtime.execute("read_docx", {"path": "a.docx", "options": {"revision_mode": "private-input"}})
        assert response.error["code"] == "INVALID_ARGUMENT"
        assert "private-input" not in str(response.error)
        assert len(response.error["message"]) < 300
        assert runtime.execute("get_runtime_info", {}).data["documents"] == 0


def test_inspection_stays_lightweight_after_full_session_upgrade() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        first = runtime.execute("inspect_document", {"path": "xlsx/xlsx-empty.xlsx"})
        identifier = first.data["document_id"]
        full = runtime.execute("inspect_document", {"document_id": identifier, "full_parse": True})
        assert full.error is None and "report" in full.data
        assert runtime.execute("inspect_document", {"document_id": identifier}).data == first.data


def test_mcp_binary_uri_and_chunk_fallback_share_lifetime() -> None:
    pytest.importorskip("mcp")
    from doctokens_agent_tools.mcp import build_server
    from doctokens_agent_tools.schemas import SourceArgs
    from mcp.shared.memory import create_connected_server_and_client_session
    from pydantic import AnyUrl

    async def verify() -> None:
        with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), max_inline_binary_bytes=1)) as runtime:
            # A valid native file supplies bytes; this tests transport, not Office content.
            with runtime._documents.acquire(SourceArgs(path="xlsx/xlsx-empty.xlsx")) as document:
                original = document.snapshot.read_bytes()
                response = runtime._presenter.binary(document, original, "application/octet-stream")
                uri = response.data["resource_uri"]
                result_id = response.data["result_id"]
                identifier = document.id
            async with create_connected_server_and_client_session(build_server(runtime)) as client:
                resource = await client.read_resource(AnyUrl(uri))
                assert base64.b64decode(resource.contents[0].blob) == original
                fragment = await client.call_tool("read_result", {"result_id": result_id})
                assert fragment.structuredContent["ok"]
                await client.call_tool("release_document", {"document_id": identifier})
                with pytest.raises(Exception, match="expired"):
                    await client.read_resource(AnyUrl(uri))
                with pytest.raises(Exception, match="unsupported"):
                    await client.read_resource(AnyUrl("doctokens://result/../../private"))

    asyncio.run(verify())
