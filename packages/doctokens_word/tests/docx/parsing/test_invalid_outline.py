"""Invalid outline values/cycles cannot be authored through normal Word UI.

Ordinary outline and formatting behavior uses native fixtures and reviewed
full-output goldens; these tests cover corrupt producer inputs only.
"""

from __future__ import annotations

import pytest
from _word_packages import _make_docx
from doctokens_word import parse_docx

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _output(body: str) -> str:
    return (
        '<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final">'
        f'<body><page number="1" />{body}</body></document>'
    )


@pytest.mark.parametrize("value", [None, "-1", "10", "bad"])
@pytest.mark.parametrize("scope", ["paragraph", "style"])
def test_invalid_outline_falls_back_with_diagnostic(value: str | None, scope: str) -> None:
    invalid = f'<w:outlineLvl w:val="{value}"/>' if value is not None else "<w:outlineLvl/>"
    styles = (
        f'<w:styles xmlns:w="{_W}"><w:style w:styleId="Base"><w:pPr><w:outlineLvl w:val="2"/></w:pPr></w:style>'
        '<w:style w:styleId="Child"><w:basedOn w:val="Base"/>'
        + (f"<w:pPr>{invalid}</w:pPr>" if scope == "style" else "")
        + "</w:style></w:styles>"
    )
    direct = invalid if scope == "paragraph" else ""
    source = _make_docx(
        f'<w:p><w:pPr><w:pStyle w:val="Child"/>{direct}</w:pPr><w:r><w:t>X</w:t></w:r></w:p>',
        {"word/styles.xml": styles},
    )
    result = parse_docx(source)
    assert result.text == _output("<h3>X</h3>")
    warnings = [warning for warning in result.report.warnings if warning.code == "INVALID_OUTLINE_LEVEL"]
    assert len(warnings) == 1
    assert warnings[0].locator == ("word/document.xml:b1" if scope == "paragraph" else "word/styles.xml")


def test_cyclic_style_heading_is_bounded() -> None:
    source = _make_docx(
        '<w:p><w:pPr><w:pStyle w:val="A"/></w:pPr><w:r><w:t>X</w:t></w:r></w:p>',
        {
            "word/styles.xml": f'<w:styles xmlns:w="{_W}"><w:style w:styleId="A"><w:basedOn w:val="B"/></w:style>'
            '<w:style w:styleId="B"><w:basedOn w:val="A"/></w:style></w:styles>'
        },
    )
    result = parse_docx(source)
    assert result.text == _output("<p>X</p>")
    assert "STYLE_INHERITANCE_CYCLE" in {warning.code for warning in result.report.warnings}
