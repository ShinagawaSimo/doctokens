"""render_window: slide selection, span clamping, last-slide shorthand."""

from __future__ import annotations

import unittest

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import Density, render_window


class RenderWindowTests(unittest.TestCase):
    def test_single_slide_window(self) -> None:
        text = render_window(rich_deck_pptx(), slide=2, density=Density.STRUCTURAL)
        self.assertTrue(text.startswith("density=structural\n"))
        self.assertIn("<slide n=2 hidden>", text)
        self.assertNotIn("<slide n=1>", text)

    def test_span_clamps_at_end(self) -> None:
        text = render_window(rich_deck_pptx(), slide=2, span=5, density=Density.STRUCTURAL)
        self.assertIn("<slide n=2 hidden>", text)
        self.assertNotIn("<slide n=1>", text)

    def test_negative_slide_selects_last(self) -> None:
        text = render_window(rich_deck_pptx(), slide=-1, density=Density.STRUCTURAL)
        self.assertIn("<slide n=2 hidden>", text)
        self.assertNotIn("<slide n=1>", text)

    def test_window_keeps_comments(self) -> None:
        text = render_window(rich_deck_pptx(), slide=1, density=Density.STRUCTURAL)
        self.assertIn("<!-- supplemental -->", text)
        self.assertIn("<comment id=cmt1", text)

    def test_out_of_range_yields_header_only(self) -> None:
        text = render_window(rich_deck_pptx(), slide=99, density=Density.PLAIN)
        self.assertEqual(text, "density=plain\n")

    def test_unknown_density_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "density"):
            render_window(rich_deck_pptx(), slide=1, density="typo")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
