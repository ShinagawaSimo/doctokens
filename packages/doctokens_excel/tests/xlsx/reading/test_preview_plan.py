"""Preview extraction budgets on an existing native workbook."""

from unittest.mock import patch

import pytest
from doctokens_excel import parse_xlsx
from doctokens_excel.xlsx.parsing.modules.workbook.string_text import read_string
from doctokens_excel.xlsx.parsing.modules.worksheets.cells import _parse_cell

from test_support.paths import REPO_ROOT

FIXTURES = REPO_ROOT / "test_support/fixtures/xlsx"


@pytest.mark.parametrize("density", ["plain", "structural", "semantic"])
def test_preview_materializes_only_its_row_budget_and_reports_that_scope(density: str) -> None:
    # Reduce only the work budget on a native input; this does not define new
    # Office content or replace the fixture's reviewed complete golden.
    from doctokens_excel import open_xlsx

    source = FIXTURES / "xlsx-shared-strings.xlsx"
    with (
        patch("doctokens_excel.xlsx.parsing.modules.worksheets.preview._CELL_BUDGET", 1),
        patch("doctokens_excel.xlsx.rendering.window._CELL_BUDGET", 1),
    ):
        with open_xlsx(source) as session:
            expected = session.render(density=density, sheet="Sheet1")
        with (
            patch("doctokens_excel.xlsx.parsing.modules.worksheets.scanner._parse_cell", wraps=_parse_cell) as decoded,
            patch("doctokens_excel.xlsx.parsing.modules.workbook.shared_strings.read_string", wraps=read_string) as strings,
        ):
            result = parse_xlsx(source, density=density, sheet="Sheet1")
        assert result.text == expected.text
        assert result.selection == expected.selection
        assert decoded.call_count == result.report.manifest["cellCount"] == 1
        assert strings.call_count == 1
