"""Unpaired UTF-16 surrogates cannot be entered as valid Unicode in native Office."""

import pytest
from doctokens_excel.xlsx.parsing.modules.workbook.string_text import decode_xstring


@pytest.mark.parametrize(("source", "code"), [("_xD800_", "D800"), ("_xDC00_", "DC00"), ("_xDFFF_", "DFFF")])
def test_unpaired_surrogate_has_explicit_safe_output_and_diagnostic(source: str, code: str) -> None:
    diagnostics: list[tuple[str, str]] = []
    assert decode_xstring(source, lambda name, message: diagnostics.append((name, message))) == "�"
    assert diagnostics == [
        ("XSTRING_CHARACTER_UNREPRESENTABLE", f"Saved character U+{code} cannot be represented in XML 1.0; emitted U+FFFD.")
    ]
