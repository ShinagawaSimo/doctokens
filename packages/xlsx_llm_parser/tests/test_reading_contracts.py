"""Public diagnostics, locale selection and read-session immutability."""

from pathlib import Path

import pytest
from xlsx_llm_parser import ParseOptions, open_xlsx, parse_xlsx

from test_support.update_goldens import DENSITIES, golden_text

SUPPORT = Path(__file__).resolve().parents[3] / "test_support"
DATE_FILE = SUPPORT / "fixtures/xlsx/xlsx-format-date-test.xlsx"


@pytest.mark.parametrize("density", DENSITIES)
def test_explicit_english_locale_full_output(density: str) -> None:
    # The full API golden fixes the authorized en-US policy, not an OS default.
    suffix = "txt" if density == "plain" else "xml"
    golden = SUPPORT / f"golden/xlsx/xlsx-format-date-test.en-US.{density}.{suffix}"
    result = parse_xlsx(DATE_FILE, density=density, options=ParseOptions(locale="en-US"))
    assert golden_text(result.text, density) == golden.read_bytes().decode("utf-8")


@pytest.mark.parametrize("density", DENSITIES)
@pytest.mark.parametrize("stem", ["xlsx-format-date-test", "xlsx-format-percent", "xlsx-date-1904"])
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
