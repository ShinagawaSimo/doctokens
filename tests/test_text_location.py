"""Search pagination, scope validation and transport on existing native files."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from docx_llm_parser import open_docx
from ooxml_llm_core.text_search import TextSearchOptions
from xlsx_llm_parser import XlsxResourceCatalog, open_xlsx

FIXTURES = Path(__file__).resolve().parents[1] / "test_support/fixtures"


@pytest.mark.parametrize("source,query", [("docx/docx-paragraph.docx", "paragraph"), ("xlsx/xlsx-shared-strings.xlsx", "text")])
def test_text_match_pagination_is_independent_of_character_continuation(source: str, query: str) -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        all_matches = runtime.execute("find_document_text", {"path": source, "query": query})
        assert all_matches.error is None
        expected = all_matches.data["parts"]
        gathered = []
        offset = 0
        while offset is not None:
            page = runtime.execute(
                "find_document_text",
                {"document_id": all_matches.data["document_id"], "query": query, "limit": 1, "offset": offset},
            )
            assert page.error is None
            gathered.extend(page.data["parts"])
            offset = page.data["next_offset"]
        assert gathered == expected
        # The native document supplies content; only search casing/transport is under test.
        insensitive = runtime.execute("find_document_text", {"path": source, "query": query.upper(), "case_sensitive": False})
        assert insensitive.error is None and insensitive.data["parts"] == expected
        assert runtime.execute("release_document", {"document_id": all_matches.data["document_id"]}).data["released"]


@pytest.mark.parametrize(
    "options",
    [{"offset": -1}, {"limit": 0}, {"limit": 201}, {"context_before": -1}, {"context_after": 4001}, {"case_sensitive": "true"}],
)
def test_search_options_reject_invalid_budgets(options: dict) -> None:
    with pytest.raises(ValueError):
        TextSearchOptions(**options)


def test_search_never_searches_generated_xml_and_checks_session_lifetime() -> None:
    session = open_docx(FIXTURES / "docx/docx-paragraph.docx")
    with session:
        assert not session.find_text("<document").matches
        assert not session.find_text(".*").matches  # A literal query, never a regex wildcard.
        with pytest.raises(ValueError):
            session.find_text("")
    with pytest.raises(RuntimeError, match="not open"):
        session.find_text("paragraph")


def test_light_catalog_does_not_read_cell_values_and_does_not_force_tool_session() -> None:
    with (
        patch("xlsx_llm_parser.parsing.runner._parse_shared_strings", side_effect=AssertionError("shared strings loaded")),
        patch("xlsx_llm_parser.parsing.runner.parse_sheet", side_effect=AssertionError("worksheet cells loaded")),
        patch("xlsx_llm_parser.parsing.runner.parse_styles", side_effect=AssertionError("styles loaded")),
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
    ):
        result = runtime.execute("list_document_resources", {"path": "xlsx/xlsx-shared-strings.xlsx"})
        assert result.error is None
        assert runtime.execute("get_runtime_info", {}).data["sessions"] == 0
        assert runtime.execute("list_document_resources", {"document_id": result.data["document_id"]}).data == result.data
    with XlsxResourceCatalog(FIXTURES / "xlsx/xlsx-shared-strings.xlsx") as catalog:
        directory = catalog.resources
    with open_xlsx(FIXTURES / "xlsx/xlsx-shared-strings.xlsx") as workbook:
        assert directory == workbook.resources
    with pytest.raises(RuntimeError, match="not open"):
        _ = catalog.resources


def test_search_scope_validation_precedes_expensive_session_creation() -> None:
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        patch("doctokens_agent_tools.documents.DocumentStore.session", side_effect=AssertionError("session allocated")),
    ):
        for source, options in (
            ("docx/docx-paragraph.docx", {"sheets": ["Sheet1"]}),
            ("xlsx/xlsx-empty.xlsx", {"include_headers_footers": True}),
        ):
            result = runtime.execute("find_document_text", {"path": source, "query": "text", **options})
            assert result.error is not None and result.error["code"] == "INVALID_ARGUMENT"


def test_selected_xlsx_text_search_does_not_allocate_a_full_session() -> None:
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        patch("doctokens_agent_tools.documents.DocumentStore.session", side_effect=AssertionError("full workbook loaded")),
    ):
        response = runtime.execute(
            "find_document_text",
            {
                "path": "xlsx/xlsx-shared-strings.xlsx",
                "query": "text",
                "sheets": ["Sheet1"],
            },
        )
        assert response.error is None and response.data["parts"]
        shorter = runtime.execute(
            "find_document_text",
            {
                "document_id": response.data["document_id"],
                "query": "text",
                "sheets": ["Sheet1"],
                "context_before": 0,
                "context_after": 0,
            },
        )
        assert shorter.error is None
        assert [part["selection"] for part in shorter.data["parts"]] == [part["selection"] for part in response.data["parts"]]
        assert all(
            len(short["text"]) <= len(full["text"])
            for short, full in zip(shorter.data["parts"], response.data["parts"], strict=True)
        )


def test_format_programs_are_compiled_per_code_and_owned_by_one_parse() -> None:
    from xlsx_llm_parser.parsing.modules.styles.number_formats.program import FormatProgram

    with patch("xlsx_llm_parser.parsing.modules.styles.index.FormatProgram", wraps=FormatProgram) as compiled:
        with open_xlsx(FIXTURES / "xlsx/xlsx-date-time.xlsx") as workbook:
            first_calls = compiled.call_count
            assert first_calls > 0
            keys = [call.args for call in compiled.call_args_list]
            assert len(keys) == len(set(keys))
            workbook.render(density="semantic")
            assert compiled.call_count == first_calls
        with open_xlsx(FIXTURES / "xlsx/xlsx-date-time.xlsx"):
            assert compiled.call_count == first_calls * 2
