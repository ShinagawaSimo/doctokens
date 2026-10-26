"""Public diagnostics, locale selection and read-session immutability."""

import pytest
from doctokens_excel import open_xlsx, parse_xlsx

from test_support.paths import REPO_ROOT
from test_support.update_goldens import DENSITIES

SUPPORT = REPO_ROOT / "test_support"


@pytest.mark.parametrize("density", DENSITIES)
@pytest.mark.parametrize("stem", ["xlsx-format-percent", "xlsx-date-1904"])
def test_unavailable_formula_bar_has_no_diagnostic(stem: str, density: str) -> None:
    result = parse_xlsx(SUPPORT / f"fixtures/xlsx/{stem}.xlsx", density=density)
    assert result.report.warnings == ()


def test_reading_projections_do_not_mutate_session_queries() -> None:
    source = SUPPORT / "fixtures/xlsx/xlsx-blank-styled.xlsx"
    with open_xlsx(source) as session:
        before = session.render(sheet="Sheet1", range_spec="A1:C1").text
        for density in DENSITIES:
            session.render(density=density)
            session.render(density=density, sheet="Sheet1")
        assert session.render(sheet="Sheet1", range_spec="A1:C1").text == before
