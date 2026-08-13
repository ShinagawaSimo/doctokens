"""iter_slides streaming: one chunk per slide, density header, start_slide, comments tail."""

from __future__ import annotations

import unittest

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import Density, iter_slides, parse_pptx


class IterSlidesTests(unittest.TestCase):
    def test_structural_chunks_per_slide(self) -> None:
        chunks = list(iter_slides(rich_deck_pptx(), density=Density.STRUCTURAL))
        self.assertEqual(len(chunks), 3)  # slide 1, slide 2, comments tail
        self.assertTrue(chunks[0].startswith("density=structural\n"))
        self.assertIn("<slide n=1>", chunks[0])
        self.assertIn("<slide n=2 hidden>", chunks[1])
        self.assertIn("<!-- supplemental -->", chunks[2])
        self.assertNotIn("<slide n=2", chunks[0])

    def test_plain_chunks(self) -> None:
        chunks = list(iter_slides(rich_deck_pptx(), density=Density.PLAIN))
        self.assertEqual(len(chunks), 3)
        self.assertTrue(chunks[0].startswith("density=plain\n"))
        self.assertIn("=== Slide 1 ===", chunks[0])
        self.assertIn("=== Slide 2 ===", chunks[1])
        self.assertIn("[Comments]", chunks[2])

    def test_start_slide_skips_earlier_slides(self) -> None:
        chunks = list(iter_slides(rich_deck_pptx(), density=Density.STRUCTURAL, start_slide=2))
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].startswith("density=structural\n"))
        self.assertIn("<slide n=2 hidden>", chunks[0])
        self.assertNotIn("<slide n=1>", chunks[0])

    def test_deck_without_comments_yields_slide_chunks_only(self) -> None:
        deck = rich_deck_pptx()
        chunks = list(iter_slides(deck, density=Density.PLAIN, start_slide=1))
        joined = "".join(chunks)
        self.assertEqual(joined, parse_pptx(deck, density=Density.PLAIN))

    def test_stream_true_matches_iter_slides(self) -> None:
        deck = rich_deck_pptx()
        streamed = list(parse_pptx(deck, density=Density.STRUCTURAL, stream=True))
        self.assertEqual(streamed, list(iter_slides(deck, density=Density.STRUCTURAL)))

    def test_unknown_density_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "density"):
            list(iter_slides(rich_deck_pptx(), density="typo"))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
