"""Native-only consumers, index mapping and opaque body/binary transport."""

from __future__ import annotations

import asyncio
import base64
import copy
import json

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_agent_tools.contracts.models import BinaryAttachment, ToolResponse

from test_support.paths import REPO_ROOT

pytest.importorskip("mcp")
from doctokens_agent_tools.mcp.projection import project_response
from doctokens_agent_tools.mcp.server import build_server
from mcp.shared.memory import create_connected_server_and_client_session

FIXTURES = REPO_ROOT / "test_support/fixtures"


def test_directory_and_errors_are_native_visible() -> None:
    async def verify() -> None:
        with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
            async with create_connected_server_and_client_session(build_server(runtime)) as client:
                result = await client.call_tool("inspect_document", {"path": "xlsx/xlsx-empty.xlsx"})
                assert len(result.content) == 1
                native = json.loads(result.content[0].text)
                assert native == result.structuredContent["data"]
                identifier = native["document_id"]
                invalid = await client.call_tool("read_docx", {"document_id": identifier, "page_start": 0})
                assert invalid.isError
                native_error = json.loads(invalid.content[0].text)["error"]
                assert native_error["code"] == "INVALID_ARGUMENT"
                assert native_error["message"] == invalid.structuredContent["error"]["message"]
                release = await client.call_tool("release_document", {"document_id": identifier})
                assert json.loads(release.content[0].text)["released"]

    asyncio.run(verify())


def test_search_locators_and_match_continuation_use_structured_metadata() -> None:
    async def verify() -> None:
        with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
            async with create_connected_server_and_client_session(build_server(runtime)) as client:
                result = await client.call_tool(
                    "find_document_text", {"path": "docx/docx-paragraph.docx", "query": "paragraph", "limit": 1}
                )
                assert not result.isError
                structured = result.structuredContent["data"]
                assert "page_start" in structured["parts"][0]["selection"]
                # Full consumers retrieve the same single body by content_index.
                assert structured["parts"][0]["content_index"] == 0
                assert len(result.content) == 1 and "text" not in structured["parts"][0]

    asyncio.run(verify())


def test_projection_preserves_multiple_and_unstarted_parts_without_mutating_response() -> None:
    # Arbitrary transport payloads isolate block mapping from Office semantics.
    response = ToolResponse(
        {
            "document_id": "snapshot",
            "next_offset": 21,
            "parts": [
                {"text": "甲 <body/>", "selection": {"page_start": 1}},
                {"selection": {"page_start": 2}, "result_id": "later", "next_offset": 0},
                {"text": "乙 body", "selection": {"page_start": 3}, "result_id": "tail", "next_offset": 6},
            ],
        }
    )
    before = copy.deepcopy(response.data)
    result = project_response(response)
    parts = result.structuredContent["data"]["parts"]
    assert response.data == before
    assert "content_index" not in parts[1]
    assert result.content[parts[0]["content_index"]].text == "甲 <body/>"
    assert result.content[parts[2]["content_index"]].text == "乙 body"
    assert all("text" not in part for part in parts)
    assert len(result.content) == 2
    assert parts[1]["result_id"] == "later" and parts[1]["next_offset"] == 0
    assert result.structuredContent["data"]["next_offset"] == 21


def test_json_fragments_and_base64_use_structured_navigation() -> None:
    for response, expected in (
        (
            ToolResponse({"text": '{"partial":', "media_type": "application/json", "result_id": "id", "next_offset": 11}),
            '{"partial":',
        ),
        (ToolResponse({"data": "YWJj", "encoding": "base64", "unit": "bytes", "next_offset": None}), "YWJj"),
    ):
        result = project_response(response)
        data = result.structuredContent["data"]
        assert result.content[data["content_index"]].text == expected
        assert "text" not in data and "data" not in data
        assert data["next_offset"] == response.data["next_offset"]
        assert len(result.content) == 1


@pytest.mark.parametrize("media_type", ["image/png", "image/jpeg", "image/webp", "image/gif"])
def test_supported_images_keep_native_content_and_only_metadata_is_text(media_type) -> None:
    response = ToolResponse(
        {"document_id": "doc", "length": 3, "media_type": media_type, "result_id": "id", "resource_uri": "doctokens://result/id"},
        attachments=(BinaryAttachment(b"abc", media_type),),
    )
    result = project_response(response)
    assert [c.type for c in result.content] == ["text", "image"]
    assert base64.b64decode(result.content[1].data) == b"abc"
    assert "YWJj" not in result.content[0].text
