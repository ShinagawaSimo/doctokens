"""Range reading tests — render_range with A1-style bounds."""

import unittest

from doctokens_excel import parse_xlsx
from doctokens_excel.xlsx.parsing.plan import XlsxFeature, XlsxParsePlan

from test_support.paths import REPO_ROOT

FIXTURE = REPO_ROOT / "test_support/fixtures/xlsx/xlsx-empty.xlsx"
VALUES = FIXTURE.with_name("xlsx-sparse.xlsx")


class RangeReadingTests(unittest.TestCase):
    def test_range_plan_limits_sheet_and_skips_formula_ir_for_plain_output(self) -> None:
        plan = XlsxParsePlan.range("plain", "Data", (1, 2, 3, 10))
        self.assertEqual(plan.sheet_names, frozenset(("Data",)))
        self.assertEqual(plan.cell_window, (1, 2, 3, 10))
        self.assertFalse(plan.needs(XlsxFeature.FORMULAS))
        self.assertTrue(plan.needs(XlsxFeature.DRAWINGS))

    def test_range_sheet_not_found(self) -> None:
        """Unknown sheet name raises KeyError."""
        with self.assertRaises(KeyError):
            parse_xlsx(FIXTURE, sheet="NoSuch", range_spec="A1:B2")

    def test_invalid_range_raises(self) -> None:
        for spec in ("", "A0", "A2:A1", "B1:A1", "20:10", "0:1", "A1:B", "XFE1", "A1048577", "Sheet1!A1"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                parse_xlsx(FIXTURE, sheet="Sheet1", range_spec=spec)

    def test_single_cell_and_rectangle_are_equivalent(self) -> None:
        single = parse_xlsx(VALUES, sheet="Sheet1", range_spec="B2")
        rectangle = parse_xlsx(VALUES, sheet="Sheet1", range_spec="B2:B2")
        self.assertEqual(single.text, rectangle.text)

    def test_whole_rows_and_full_width_rectangle_are_equivalent(self) -> None:
        rows = parse_xlsx(VALUES, sheet="Sheet1", range_spec="2:5")
        rectangle = parse_xlsx(VALUES, sheet="Sheet1", range_spec="A2:XFD5")
        self.assertEqual(rows.text, rectangle.text)


if __name__ == "__main__":
    unittest.main()
