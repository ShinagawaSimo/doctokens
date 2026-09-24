"""Test-side structural guardrails for serialized DTX."""

from pathlib import Path

import pytest

from test_support.dtx_contract import validate_dtx_structure

ROOT = Path(__file__).parents[3]


@pytest.mark.parametrize("format_name", ["docx", "pptx"])
@pytest.mark.parametrize("density", ["structural", "semantic"])
def test_existing_goldens_obey_dtx_structure(format_name: str, density: str) -> None:
    name = "parsed.xml" if density == "semantic" else "structural.xml"
    value = (ROOT / "test_support" / "golden" / format_name / name).read_text(encoding="utf-8")
    validate_dtx_structure(value)


def test_valid_xlsx_grid_obeys_dtx_structure() -> None:
    value = (
        '<workbook schema="doctokens-xml" version="1.0" format="xlsx" density="semantic">'
        '<sheet name="Data"><grid ref="A1:C2"><tr number="2">'
        '<cell column="B" formula="SUM(B1:B2)" formula-range="B2:C2" spill-range="B2:C2">3</cell>'
        "</tr></grid></sheet></workbook>"
    )
    validate_dtx_structure(value)


@pytest.mark.parametrize(
    "body",
    [
        "<surprise />",
        '<page number="0" />',
        '<page number="1">text</page>',
    ],
)
def test_unknown_or_invalid_page_is_rejected(body: str) -> None:
    value = f'<document schema="doctokens-xml" version="1.0" format="docx" density="structural"><body>{body}</body></document>'
    with pytest.raises(ValueError):
        validate_dtx_structure(value)


@pytest.mark.parametrize("cell_attrs", ['column="1"', 'spill-range="bad"', 'spill-from="A0"'])
def test_invalid_cell_coordinates_are_rejected(cell_attrs: str) -> None:
    value = (
        '<workbook schema="doctokens-xml" version="1.0" format="xlsx" density="structural">'
        f'<sheet name="Data"><grid ref="A1:B2"><tr number="1"><cell {cell_attrs}/></tr></grid></sheet></workbook>'
    )
    with pytest.raises(ValueError):
        validate_dtx_structure(value)
