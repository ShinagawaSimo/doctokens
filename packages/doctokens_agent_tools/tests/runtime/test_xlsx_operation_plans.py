"""Minimal-operation ownership and work budgets, using existing native files."""

from __future__ import annotations

from unittest.mock import patch

from doctokens_agent_tools import RuntimeConfig, ToolRuntime
from doctokens_excel import open_xlsx
from doctokens_excel.xlsx.parsing.modules.worksheets.cells import _parse_cell

from test_support.paths import REPO_ROOT

FIXTURES = REPO_ROOT / "test_support/fixtures/xlsx"


def test_limit_stops_cell_conversion_and_cold_query_does_not_open_a_full_session() -> None:
    args = {"sheet": "Sheet1", "range_spec": "A1:A3", "header_row": 1, "limit": 1}
    source = FIXTURES / "xlsx-shared-strings.xlsx"
    with open_xlsx(source) as session:
        expected = session.query_data(**args).text
    with (
        ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime,
        patch("doctokens_agent_tools.state.documents.DocumentStore.session", side_effect=AssertionError("full session opened")),
        patch("doctokens_excel.xlsx.parsing.modules.worksheets.scanner._parse_cell", wraps=_parse_cell) as converted,
    ):
        response = runtime.execute("query_xlsx_data", {"path": str(source), **args})
        assert response.error is None and response.data["parts"][0]["text"] == expected
        assert [call.args[5] for call in converted.call_args_list] == ["A1", "A2"]
        assert runtime.execute("get_runtime_info", {}).data["sessions"] == 0


def test_existing_full_session_is_reused_for_queries() -> None:
    with ToolRuntime(RuntimeConfig(allowed_roots=(FIXTURES,))) as runtime:
        inspected = runtime.execute("inspect_document", {"path": "xlsx-shared-strings.xlsx", "full_parse": True})
        with patch("doctokens_agent_tools.runtime.operations.query_xlsx", side_effect=AssertionError("cold parse used")):
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
