"""Pending PPTX list files cover menu-supported schemes. Nonpositive counters and schemes absent from the Simplified
Chinese menu remain compatibility exceptions.
"""

import unittest

from ooxml_llm_core.text_numbering import alpha_number, format_drawingml_autonumber, roman_number


class TextNumberingTests(unittest.TestCase):
    def test_alpha_and_roman_sequences_support_large_values(self) -> None:
        self.assertEqual(alpha_number(1, upper=False), "a")
        self.assertEqual(alpha_number(27, upper=True), "AA")

    def test_drawingml_schemes_apply_punctuation(self) -> None:
        expected = {
            "arabicPlain": "3",
            "arabicPeriod": "3.",
            "arabicParenR": "3)",
            "arabicParenBoth": "(3)",
            "alphaUcPeriod": "C.",
            "alphaLcParenR": "c)",
            "romanUcPeriod": "III.",
            "romanLcParenBoth": "(iii)",
        }
        for scheme, value in expected.items():
            with self.subTest(scheme=scheme):
                self.assertEqual(format_drawingml_autonumber(3, scheme), value)

    def test_drawingml_full_width_and_circle_schemes(self) -> None:
        self.assertEqual(format_drawingml_autonumber(12, "arabicDbPeriod"), "１２．")
        self.assertEqual(format_drawingml_autonumber(10, "circleNumDbPlain"), "⑩")
        self.assertEqual(format_drawingml_autonumber(11, "circleNumDbPlain"), "11")

    def test_drawingml_scheme_families_and_non_positive_values(self) -> None:
        self.assertEqual(alpha_number(0, upper=False), "0")
        self.assertEqual(roman_number(0), "0")
        expected = {
            "alphaLcParenBoth": "(c)",
            "alphaLcParenRight": "c)",
            "alphaLcPeriod": "c.",
            "alphaUcParenBoth": "(C)",
            "alphaUcParenRight": "C)",
            "romanLcParenRight": "iii)",
            "romanLcPeriod": "iii.",
            "romanUcParenBoth": "(III)",
            "romanUcParenRight": "III)",
            "romanUcPeriod": "III.",
            "arabic1Minus": "3",
            "arabicDbPlain": "３",
            "arabicDbPeriod": "３．",
            "ea1ChsPeriod": "3.",
            "unsupported": "3.",
        }
        for scheme, value in expected.items():
            with self.subTest(scheme=scheme):
                self.assertEqual(format_drawingml_autonumber(3, scheme), value)
