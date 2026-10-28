"""Invalid symbol encodings and extreme nesting cannot be saved through normal Word UI."""

from __future__ import annotations

import pytest
from _word_packages import _make_docx
from doctokens_word import parse_docx


@pytest.mark.parametrize("code", ["", "XYZ1", "110000", "-001"])
def test_invalid_symbol_code_is_visible_and_diagnosed(code: str) -> None:
    result = parse_docx(_make_docx(f'<w:p><w:r><w:sym w:font="Symbol" w:char="{code}"/></w:r></w:p>'))
    assert result.text == (
        '<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final">'
        '<body><page number="1" /><p>�</p></body></document>'
    )
    warnings = [warning for warning in result.report.warnings if warning.code == "INVALID_SYMBOL_CODE"]
    assert len(warnings) == 1
    assert warnings[0].locator == "word/document.xml:b1"


def test_extreme_ruby_nesting_is_bounded() -> None:
    content = "<w:r><w:t>Too deep</w:t></w:r>"
    for _ in range(34):
        content = f"<w:r><w:ruby><w:rt><w:r><w:t>Guide</w:t></w:r></w:rt><w:rubyBase>{content}</w:rubyBase></w:ruby></w:r>"
    result = parse_docx(_make_docx(f"<w:p>{content}</w:p>"))
    assert result.text == (
        '<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final">'
        '<body><page number="1" /></body></document>'
    )
    assert [warning.code for warning in result.report.warnings if warning.code == "RUBY_NESTING_LIMIT"] == ["RUBY_NESTING_LIMIT"]
