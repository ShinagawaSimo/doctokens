"""Minimal-operation ownership and work budgets, using existing native files."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from xlsx_llm_parser import find_xlsx_cells, open_xlsx, query_xlsx
from xlsx_llm_parser.parsing.modules.worksheets.cells import _parse_cell
from xlsx_llm_parser.parsing.modules.worksheets.scanner import parse_sheet

FIXTURES = Path(__file__).resolve().parents[1] / "test_support/fixtures/xlsx"


@pytest.mark.parametrize(
    "extra,expected_data_refs",
    [({}, ["A2"]), ({"where": [{"column": "C", "op": "gt", "value": 0}]}, ["A2", "C2"])],
)
def test_query_projects_dependencies_before_converting_cells(extra: dict, expected_data_refs: list[str]) -> None:
    source = FIXTURES / "xlsx-formula-horizontal.xlsx"
    args = {"sheet": "Sheet1", "range_spec": "A1:C2", "header_row": 1, "select": ["A"], "limit": 1, **extra}
    with open_xlsx(source) as session:
        expected = session.query_data(**args).text
    with patch("xlsx_llm_parser.parsing.modules.worksheets.scanner._parse_cell", wraps=_parse_cell) as converted:
        assert query_xlsx(source, **args).text == expected
        # Complete native header identities remain available, but only output
        # and filter columns are converted for data rows.
        refs = [call.args[5] for call in converted.call_args_list]
        assert refs == ["A1", "B1", "C1", *expected_data_refs]


def test_limit_stops_cell_conversion_and_cold_query_does_not_open_a_full_session() -> None:
    args = {"sheet": "Sheet1", "range_spec": "A1:A3", "header_row": 1, "limit": 1}
    source = FIXTURES / "xlsx-shared-strings.xlsx"
    with open_xlsx(source) as session:
        expected = session.query_data(**args).text
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        patch("doctokens_agent_tools.documents.DocumentStore.session", side_effect=AssertionError("full session opened")),
        patch("xlsx_llm_parser.parsing.modules.worksheets.scanner._parse_cell", wraps=_parse_cell) as converted,
    ):
        response = runtime.execute("query_xlsx_data", {"path": str(source), **args})
        assert response.error is None and response.data["parts"][0]["text"] == expected
        assert [call.args[5] for call in converted.call_args_list] == ["A1", "A2"]
        assert runtime.execute("get_runtime_info", {}).data["sessions"] == 0


def test_query_does_not_scan_other_worksheets() -> None:
    source = FIXTURES / "xlsx-formula-cross-sheet.xlsx"
    with patch("xlsx_llm_parser._operation_source.parse_sheet", wraps=parse_sheet) as scanned:
        query_xlsx(source, sheet="Data", range_spec="A1:A2", header_row=1)
        assert scanned.call_count == 2  # Header/tail declarations, followed by value rows.
        assert len({call.args[1] for call in scanned.call_args_list}) == 1


@pytest.mark.parametrize("kind", ["formula", "comment", "hyperlink", "definedName"])
def test_field_search_skips_shared_strings_styles_and_nonmatching_cell_projections(kind: str) -> None:
    source = FIXTURES / "xlsx-formula-horizontal.xlsx"
    with open_xlsx(source) as session:
        expected = session.find_cells("2", kind=kind).text
    with (
        patch("xlsx_llm_parser.parsing.runner._parse_shared_strings", side_effect=AssertionError("strings loaded")),
        patch("xlsx_llm_parser.parsing.runner.parse_styles", side_effect=AssertionError("styles loaded")),
        patch("xlsx_llm_parser.parsing.modules.worksheets.scanner._parse_cell", wraps=_parse_cell) as converted,
    ):
        assert find_xlsx_cells(source, "2", kind=kind).text == expected
        refs = [call.args[5] for call in converted.call_args_list]
        assert refs == (["A1", "B1", "C1"] if kind == "formula" else [])


def test_existing_full_session_is_reused_for_queries() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        inspected = runtime.execute("inspect_document", {"path": "xlsx-shared-strings.xlsx", "full_parse": True})
        with patch("doctokens_agent_tools.operations.query_xlsx", side_effect=AssertionError("cold parse used")):
            response = runtime.execute(
                "query_xlsx_data",
                {
                    "document_id": inspected.data["document_id"],
                    "sheet": "Sheet1",
                    "range_spec": "A1:A3",
                    "header_row": 1,
                },
            )
            assert response.error is None


def test_limited_query_validates_trailing_xml_and_releases_the_reader() -> None:
    # A corrupt tail cannot be saved by Office; damage a private copy of a
    # native file rather than manufacturing ordinary document content.
    source = io.BytesIO()
    with ZipFile(FIXTURES / "xlsx-shared-strings.xlsx") as original, ZipFile(source, "w") as damaged:
        for entry in original.infolist():
            value = original.read(entry.filename)
            if entry.filename == "xl/worksheets/sheet1.xml":
                value += b"<broken"
            damaged.writestr(entry, value)
    from ooxml_llm_core.package import PackageReader

    close = PackageReader.__exit__
    with patch.object(PackageReader, "__exit__", autospec=True, side_effect=close) as closed:
        with pytest.raises(ET.ParseError):
            query_xlsx(source.getvalue(), sheet="Sheet1", range_spec="A1:A3", header_row=1, limit=1)
        assert closed.call_count == 1
