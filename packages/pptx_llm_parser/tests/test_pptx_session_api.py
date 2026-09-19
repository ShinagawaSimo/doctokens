"""Session selection, iteration, validation, and resources."""

from __future__ import annotations

import unittest

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import open_pptx, parse_pptx
from pptx_llm_parser.core.models import ParseOptions


class PptxSessionApiTests(unittest.TestCase):
    def test_selection_and_iteration_use_the_same_rendering(self) -> None:
        source = rich_deck_pptx()
        with open_pptx(source) as session:
            selected = session.render(slide=2, density="structural")
            self.assertIn("<slide n=2 hidden>", selected.text)
            self.assertNotIn("<slide n=1>", selected.text)
            self.assertEqual("".join(session.iter_render(slide=2, density="structural")), selected.text)
            self.assertTrue(session.read_resource("image", "img1"))
            self.assertIn("<chart", session.render_resource("chart", "chart1").text)
            self.assertIn("<table", session.render_resource("table", "table1", rows="1-1").text)

    def test_invalid_and_missing_values_are_explicit(self) -> None:
        source = rich_deck_pptx()
        with self.assertRaises(ValueError):
            parse_pptx(source, slide=0)
        with open_pptx(source) as session:
            self.assertTrue(session.render(slide=99).selection["empty"])
            with self.assertRaises(KeyError):
                session.render_resource("chart", "missing")
            with self.assertRaises(ValueError):
                session.read_resource("chart", "chart1")

    def test_options_validate_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_zip_entries"):
            ParseOptions(max_zip_entries=True)


if __name__ == "__main__":
    unittest.main()
