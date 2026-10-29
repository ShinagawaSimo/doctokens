"""Noncanonical scientific spelling is a producer case Excel normally rewrites."""

from doctokens_excel.xlsx.parsing.modules.worksheets.formula_refs import translate_formula


def test_unexpanded_scientific_literal_from_other_producers() -> None:
    assert translate_formula("1E5*A1", 0, 1) == "1E5*A2"
