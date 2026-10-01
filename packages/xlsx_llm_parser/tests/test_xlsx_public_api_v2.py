"""Focused XLSX tests for the rewritten public boundary."""

from __future__ import annotations

import unittest
from pathlib import Path

from xlsx_llm_parser import ParseResult, open_xlsx, parse_xlsx


class PublicApiV2Tests(unittest.TestCase):
    def test_parse_result_and_session(self) -> None:
        source = Path(__file__).resolve().parents[3] / "test_support/fixtures/xlsx/xlsx-value-text.xlsx"
        result = parse_xlsx(source)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.report.format, "xlsx")
        self.assertEqual(result.syntax_version, "doctokens-xml/1.0")
        self.assertEqual(result.media_type, "application/xml")
        with open_xlsx(source) as session:
            self.assertEqual(session.render(sheet="Sheet1").selection["kind"], "sheet")
        with self.assertRaisesRegex(RuntimeError, "not open"):
            session.render()


if __name__ == "__main__":
    unittest.main()
