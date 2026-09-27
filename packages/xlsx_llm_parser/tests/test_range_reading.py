"""Range reading tests — render_range with A1-style bounds."""

import unittest
from pathlib import Path

from xlsx_llm_parser import parse_xlsx
from xlsx_llm_parser.plan import XlsxFeature, XlsxParsePlan

FIXTURE = Path(__file__).resolve().parents[3] / "test_support/fixtures/xlsx/xlsx-empty.xlsx"


class RangeReadingTests(unittest.TestCase):
    def test_range_plan_limits_sheet_and_skips_formula_ir_for_plain_output(self) -> None:
        plan = XlsxParsePlan.range("plain", "Data", (1, 2, 3, 10))
        self.assertEqual(plan.sheet_names, frozenset(("Data",)))
        self.assertEqual(plan.cell_window, (1, 2, 3, 10))
        self.assertFalse(plan.needs(XlsxFeature.FORMULAS))
        self.assertTrue(plan.needs(XlsxFeature.DRAWINGS))
        self.assertIn("worksheets.plain_cells", plan.module_keys)

    def test_range_sheet_not_found(self) -> None:
        """Unknown sheet name raises KeyError."""
        with self.assertRaises(KeyError):
            parse_xlsx(FIXTURE, sheet="NoSuch", range_spec="A1:B2")

    def test_invalid_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_xlsx(FIXTURE, sheet="Sheet1", range_spec="A1")  # no colon


if __name__ == "__main__":
    unittest.main()
