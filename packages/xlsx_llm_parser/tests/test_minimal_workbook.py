"""Session options and lifecycle checked with a real empty workbook."""

import unittest
from pathlib import Path

from xlsx_llm_parser import ParseOptions, open_xlsx

FIXTURE = Path(__file__).resolve().parents[3] / "test_support/fixtures/xlsx/xlsx-empty.xlsx"


class SessionOptionTests(unittest.TestCase):
    def test_session_accepts_package_options_and_exposes_report(self) -> None:
        data = FIXTURE
        with open_xlsx(data, options=ParseOptions(max_zip_entries=100)) as session:
            self.assertEqual(session.report.format, "xlsx")
            self.assertEqual(session.render().text, session.render().text)
            self.assertTrue(list(session.iter_render(density="plain")))
            session.render(sheet="Sheet1", range_spec="A1:A1")
            self.assertEqual(session.find_cells("").text, "<matches>\n")
            with self.assertRaises(KeyError):
                session.render_resource("chart", "missing")
            with self.assertRaisesRegex(ValueError, "density"):
                session.render(density="invalid")
