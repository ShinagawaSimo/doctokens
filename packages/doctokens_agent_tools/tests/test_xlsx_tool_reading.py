"""Tool routing, schema, caching and transport contracts on real XLSX files."""

from pathlib import Path
from unittest.mock import patch

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_excel import parse_xlsx

FIXTURES = Path(__file__).resolve().parents[3] / "test_support/fixtures/xlsx"


def test_default_routes_to_first_worksheet_without_opening_full_session() -> None:
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        patch("doctokens_agent_tools.operations.parse_xlsx", wraps=parse_xlsx) as parse,
        patch("doctokens_agent_tools.documents.DocumentStore.session", side_effect=AssertionError("unexpected session")),
    ):
        response = runtime.execute("read_xlsx", {"path": "xlsx-formula-cross-sheet.xlsx"})
        assert response.error is None
        assert parse.call_args.kwargs["sheet"] == "Data"
        assert parse.call_args.kwargs["range_spec"] is None
        assert response.data["parts"][0]["selection"]["sheet"] == "Data"
        assert [sheet["name"] for sheet in response.data["sheets"]] == ["Data", "Source"]


@pytest.mark.parametrize("density", ["plain", "structural", "semantic"])
def test_ranges_reuse_results_and_full_sessions(density: str) -> None:
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        patch("doctokens_agent_tools.operations.parse_xlsx", wraps=parse_xlsx) as parse,
    ):
        args = {"path": "xlsx-sparse.xlsx", "sheet": "Sheet1", "range_spec": "2:5", "density": density}
        first = runtime.execute("read_xlsx", args)
        assert first.error is None
        identifier = first.data["document_id"]
        selected = {"document_id": identifier, "sheet": "Sheet1", "range_spec": "2:5", "density": density}
        cached = runtime.execute("read_xlsx", selected)
        assert cached.error is None
        assert parse.call_count == 1
        assert cached.data["parts"] == first.data["parts"]
        assert runtime.execute("list_document_resources", {"document_id": identifier}).error is None
        assert runtime.execute("inspect_document", {"document_id": identifier, "full_parse": True}).error is None
        # A different spelling avoids the result cache and exercises session rendering.
        via_session = runtime.execute("read_xlsx", {**selected, "range_spec": "A2:XFD5"})
        assert via_session.error is None
        assert parse.call_count == 1
        assert via_session.data["parts"][0]["text"] == first.data["parts"][0]["text"]


def test_character_fragments_do_not_change_data_window_metadata() -> None:
    from dataclasses import replace

    # Only transport is under test: enlarge an already parsed native result to
    # force continuation without manufacturing an Office file or parsing golden.
    original = parse_xlsx(FIXTURES / "xlsx-format-currency-common.xlsx", sheet="Sheet1", density="structural")
    expected = original.text * 30
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,), reply_chars=2400)) as runtime,
        patch("doctokens_agent_tools.operations.parse_xlsx", return_value=replace(original, text=expected)),
    ):
        response = runtime.execute("read_xlsx", {"path": "xlsx-format-currency-common.xlsx"})
        assert response.error is None
        # Use a real result with a deliberately small host transport budget.
        part = response.data["parts"][0]
        identifier = part["result_id"]
        offset = part["next_offset"]
        fragments: list[str] = [part.get("text", "")]
        while True:
            fragment = runtime.execute("read_result", {"result_id": identifier, "offset": offset, "length": 13})
            assert fragment.error is None
            assert set(fragment.data) == {"text", "next_offset"}
            fragments.append(fragment.data["text"])
            if fragment.data["next_offset"] is None:
                break
            offset = fragment.data["next_offset"]
        assert "".join(fragments) == expected


def test_xlsx_schema_removes_full_document_but_other_formats_keep_it() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        schemas = {item.name: item.input_schema for item in runtime.list_tools()}
        assert "whole_document" not in schemas["read_xlsx"]["properties"]
        for name in ("read_docx", "read_pptx"):
            assert "whole_document" in schemas[name]["properties"]
        response = runtime.execute("read_xlsx", {"path": "xlsx-sparse.xlsx", "whole_document": True})
        assert response.error is not None and response.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.parametrize("range_spec", ["A1:H20", "10:20", "A1"])
def test_explicit_ranges_require_a_sheet(range_spec: str) -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        response = runtime.execute("read_xlsx", {"path": "xlsx-sparse.xlsx", "range_spec": range_spec})
        assert response.error is not None and response.error["code"] == "INVALID_ARGUMENT"
