"""Invalid grids and excessive logical widths cannot be authored in normal Word UI."""

from __future__ import annotations

import pytest
from _word_packages import _make_docx
from doctokens_word import parse_docx
from doctokens_word.docx.model import ParseOptions


@pytest.mark.parametrize("name", ["gridBefore", "gridAfter"])
@pytest.mark.parametrize("value", ["-1", "bad"])
def test_invalid_grid_offset_warns_and_preserves_reading(name: str, value: str) -> None:
    source = _make_docx(
        f'<w:tbl><w:tr><w:trPr><w:{name} w:val="{value}"/></w:trPr><w:tc><w:p><w:r><w:t>X</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    )
    result = parse_docx(source)
    assert result.text == (
        '<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final">'
        '<body><page number="1" /><table id="t1"><tr><td><p>X</p></td></tr></table></body></document>'
    )
    warnings = [warning for warning in result.report.warnings if warning.code == "INVALID_TABLE_GRID_OFFSET"]
    assert len(warnings) == 1
    assert warnings[0].locator == "word/document.xml"


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_logical_column_limit_must_be_positive_integer(value: object) -> None:
    with pytest.raises(ValueError, match="max_table_columns"):
        ParseOptions(max_table_columns=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("property_xml", ['<w:gridBefore w:val="1000000000"/>', '<w:gridAfter w:val="1000000000"/>'])
def test_abusive_grid_offset_is_bounded_before_output_expansion(property_xml: str) -> None:
    source = _make_docx(
        f"<w:tbl><w:tr><w:trPr>{property_xml}</w:trPr><w:tc><w:p><w:r><w:t>X</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    )
    with pytest.raises(ValueError, match="max_table_columns"):
        parse_docx(source)
