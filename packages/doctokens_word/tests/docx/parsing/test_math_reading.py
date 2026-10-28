"""Producer-specific math extensions that cannot be authored with normal Word UI."""

from __future__ import annotations

from _word_packages import _make_docx
from doctokens_word import parse_docx

_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def test_math_unknown_extension_exposes_diagnostic() -> None:
    # A producer-specific unknown namespace is an exceptional input.
    source = _make_docx(
        f'<w:p><m:oMath xmlns:m="{_M}" xmlns:u="urn:future"><u:math><m:r><m:t>a_b</m:t></m:r></u:math></m:oMath></w:p>'
    )
    result = parse_docx(source)
    assert [warning.code for warning in result.report.warnings if warning.code.startswith("MATH_")] == [
        "MATH_CONTENT_UNSUPPORTED"
    ]
