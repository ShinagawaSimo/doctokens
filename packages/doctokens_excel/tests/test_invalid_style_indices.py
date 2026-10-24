"""Corrupt style indices must not invoke Python's negative-index fallback.

Office does not save negative XF/font/fill references; these are exceptional
producer/corruption states, independent of normal native formatting goldens.
"""

from doctokens_excel.parsing.modules.styles.index import FormatIndex


def test_negative_xf_does_not_reuse_last_valid_protection_or_style() -> None:
    index = FormatIndex()
    index.register_font({"bold": True})
    index.register_fill({"fill": "#FF0000"})
    index.register_cell_format(0, "General", locked=False, formula_hidden=True)
    assert index.style_attrs(-1) == ""
    assert index.protection_attrs(-1) == ""


def test_negative_font_and_fill_references_are_not_other_records() -> None:
    index = FormatIndex()
    index.register_font({"bold": True})
    index.register_fill({"fill": "#FF0000"})
    index.register_cell_format(0, "General", font_id=-1, fill_id=-1)
    assert index.style_attrs(0) == ""
