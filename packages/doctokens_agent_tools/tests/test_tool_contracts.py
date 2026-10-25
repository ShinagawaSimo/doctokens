"""Discoverability, host budgets and snapshot lifecycle, using native valid files."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_agent_tools.presentation import Presenter
from doctokens_agent_tools.results import ResultStore

FIXTURES = Path(__file__).resolve().parents[3] / "test_support/fixtures"


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
    assert len(base64.b64decode(presenter.fragment(binary.id, 0, None).data["data"])) == limits["effective_binary_bytes"]
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
                fragment_data = fragment.structuredContent["data"]
                assert "data" not in fragment_data
                decoded = base64.b64decode(fragment.content[fragment_data["content_index"]].text)
                assert decoded == original[: len(decoded)]
                await client.call_tool("release_document", {"document_id": identifier})
                with pytest.raises(Exception, match="expired"):
                    await client.read_resource(AnyUrl(uri))
                with pytest.raises(Exception, match="unsupported"):
                    await client.read_resource(AnyUrl("doctokens://result/../../private"))

    asyncio.run(verify())


def test_mcp_small_non_image_binary_is_linked_without_automatic_base64() -> None:
    pytest.importorskip("mcp")
    from unittest.mock import AsyncMock, patch

    from doctokens_agent_tools.mcp import build_server
    from doctokens_agent_tools.schemas import SourceArgs
    from mcp.shared.memory import create_connected_server_and_client_session
    from pydantic import AnyUrl

    async def verify() -> None:
        with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
            # Only the MCP presentation policy is under test; bytes and snapshot
            # come from a valid native file, without manufacturing Office content.
            with runtime._documents.acquire(SourceArgs(path="xlsx/xlsx-empty.xlsx")) as document:
                original = document.snapshot.read_bytes()
                response = runtime._presenter.binary(document, original, "application/octet-stream")
                assert response.attachments[0].data == original  # Direct callers retain inline attachments.
            async with create_connected_server_and_client_session(build_server(runtime)) as client:
                with patch.object(runtime, "aexecute", AsyncMock(return_value=response)):
                    result = await client.call_tool(
                        "read_resource", {"document_id": document.id, "kind": "image", "resource_id": "binary"}
                    )
                assert [content.type for content in result.content] == ["text", "resource_link"]
                assert result.content[1].mimeType == "application/octet-stream"
                assert str(result.content[1].uri) == response.data["resource_uri"]
                assert result.content[1].size == len(original)
                resource = await client.read_resource(AnyUrl(response.data["resource_uri"]))
                assert base64.b64decode(resource.contents[0].blob) == original
                await client.call_tool("release_document", {"document_id": document.id})

    asyncio.run(verify())


@pytest.mark.parametrize("mode", ["compatible", "compact"])
def test_mcp_delivers_native_first_text_once_and_continues_without_repeating_metadata(mode: str) -> None:
    pytest.importorskip("mcp")
    from dataclasses import replace
    from unittest.mock import patch

    from doctokens_agent_tools.mcp import build_server
    from doctokens_excel import parse_xlsx
    from mcp.shared.memory import create_connected_server_and_client_session

    native = parse_xlsx(FIXTURES / "xlsx/xlsx-sparse.xlsx", sheet="Sheet1", density="structural")
    # Artificial length tests only opaque transport; the Office parser and its
    # reviewed output remain supplied by a native fixture.
    expected = native.text * 20

    async def verify() -> None:
        with (
            ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), reply_chars=700, mcp_output_mode=mode)) as runtime,
            patch("doctokens_agent_tools.operations.parse_xlsx", return_value=replace(native, text=expected)),
        ):
            async with create_connected_server_and_client_session(build_server(runtime)) as client:
                response = await client.call_tool("read_xlsx", {"path": "xlsx/xlsx-sparse.xlsx", "sheet": "Sheet1"})
                data = response.structuredContent["data"]
                assert not {"path", "revision", "cache_hit", "sheets", "selected_sheet"} & data.keys()
                part = data["parts"][0]
                assert "text" not in part
                assert len(response.content) == (2 if mode == "compatible" else 1)
                text = response.content[part["content_index"]].text
                assert text == expected[:700]
                offset = part["next_offset"]
                while offset is not None:
                    response = await client.call_tool(
                        "read_result", {"result_id": part["result_id"], "offset": offset, "length": 32000}
                    )
                    cursor = response.structuredContent["data"]
                    assert set(cursor) == {"content_index", "next_offset"}
                    text += response.content[cursor["content_index"]].text
                    offset = cursor["next_offset"]
                assert text == expected
                await client.call_tool("release_document", {"document_id": data["document_id"]})

    asyncio.run(verify())


def test_first_reply_budget_covers_multiple_text_parts_without_losing_unstarted_parts() -> None:
    from doctokens_agent_tools.schemas import SourceArgs

    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), reply_chars=650)) as runtime,
        runtime._documents.acquire(SourceArgs(path="xlsx/xlsx-empty.xlsx")) as document,
    ):
        # Unicode payloads verify character offsets independently of byte storage.
        first = runtime._results.put(document.id, "甲" * 700, {"selection": {"page": 1}, "media_type": "text/plain"})
        second = runtime._results.put(document.id, "乙" * 10, {"selection": {"page": 2}, "media_type": "text/plain"})
        parts = runtime._presenter.entries(document, [first, second]).data["parts"]
        assert parts[0]["text"] == "甲" * 650
        assert parts[0]["next_offset"] == 650
        assert "text" not in parts[1] and parts[1]["next_offset"] == 0
        for part, expected in zip(parts, [first.value, second.value], strict=True):
            tail = runtime.execute("read_result", {"result_id": part["result_id"], "offset": part["next_offset"]})
            assert tail.error is None and tail.data["next_offset"] is None
            assert part.get("text", "") + tail.data["text"] == expected


def test_large_metadata_includes_a_first_json_fragment_and_reassembles_without_extra_envelopes() -> None:
    import json

    from doctokens_agent_tools.schemas import SourceArgs

    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), reply_chars=650)) as runtime,
        runtime._documents.acquire(SourceArgs(path="xlsx/xlsx-empty.xlsx")) as document,
    ):
        data = runtime._presenter.metadata(document, {"items": list(range(500))}).data
        assert data["media_type"] == "application/json"
        chunks = [data["text"]]
        offset = data["next_offset"]
        while offset is not None:
            fragment = runtime.execute("read_result", {"result_id": data["result_id"], "offset": offset})
            assert fragment.error is None
            chunks.append(fragment.data["text"])
            offset = fragment.data["next_offset"]
        assert json.loads("".join(chunks)) == {"document_id": document.id, "items": list(range(500))}


def test_cached_result_evicted_before_presentation_is_readmitted_for_continuation() -> None:
    from doctokens_agent_tools.schemas import SourceArgs

    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), reply_chars=650)) as runtime,
        runtime._documents.acquire(SourceArgs(path="xlsx/xlsx-empty.xlsx")) as document,
    ):
        entry = runtime._results.put(document.id, "x" * 700, {"selection": {}, "media_type": "text/plain"})
        runtime._results.remove(entry.id)  # Simulate another document's LRU admission.
        response = runtime._presenter.entries(document, [entry])
        part = response.data["parts"][0]
        assert part["result_id"] != entry.id
        tail = runtime.execute("read_result", {"result_id": part["result_id"], "offset": part["next_offset"]})
        assert tail.error is None and part["text"] + tail.data["text"] == entry.value
