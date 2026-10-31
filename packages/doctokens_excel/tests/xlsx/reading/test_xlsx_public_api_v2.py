"""Focused XLSX tests for the rewritten public boundary."""

from __future__ import annotations

import unittest

from doctokens_excel import ParseResult, open_xlsx, parse_xlsx

from test_support.paths import REPO_ROOT


class PublicApiV2Tests(unittest.TestCase):
    def test_density_projection_is_independent_of_read_history(self) -> None:
        # Exercise formatting-cache lifetime using real files and full outputs,
        # without adding content assertions already owned by their goldens.
        for name in ("xlsx-rich-color.xlsx", "xlsx-format-number-negative-red-no-symbol.xlsx"):
            with self.subTest(name=name):
                source = REPO_ROOT / "test_support/fixtures/xlsx" / name
                fresh = {density: parse_xlsx(source, density=density) for density in ("plain", "structural", "semantic")}
                with open_xlsx(source) as session:
                    for density in ("semantic", "structural", "plain", "semantic", "plain", "structural"):
                        self.assertEqual(session.render(density=density).text, fresh[density].text)
                        self.assertEqual("".join(session.iter_render(density=density)), fresh[density].text)

    def test_parse_result_and_session(self) -> None:
        source = REPO_ROOT / "test_support/fixtures/xlsx/xlsx-value-text.xlsx"
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
