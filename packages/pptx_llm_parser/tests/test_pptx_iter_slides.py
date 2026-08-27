"""iter_slides output chunks: one chunk per slide, density header, comments tail."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import Density, iter_slides, open_pptx, parse_pptx


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
        self.assertEqual(list(iter_slides(rich_deck_pptx(), start_slide=99)), [])

    def test_start_slide_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            list(iter_slides(rich_deck_pptx(), start_slide=0))

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

    def test_read_session_exposes_report_and_reuses_parsed_presentation(self) -> None:
        with open_pptx(rich_deck_pptx()) as session:
            self.assertEqual(session.report.format, "pptx")
            self.assertIn("schemaVersion", session.report.to_dict())
            self.assertEqual(session.render(density=Density.PLAIN), session.render(density=Density.PLAIN))
            self.assertIn("<slide", session.render(density=Density.STRUCTURAL))
            self.assertIn("<slide", session.render(density=Density.SEMANTIC))
            self.assertTrue(list(session.iter_render(density=Density.PLAIN)))
            self.assertTrue(list(session.iter_render(density=Density.STRUCTURAL)))
            self.assertTrue(list(session.iter_render(density=Density.SEMANTIC)))
            self.assertIn("slide", session.render_window(slide=1, density=Density.PLAIN))
            self.assertIn("slide", session.render_window(slide=-1, density=Density.STRUCTURAL))
            self.assertEqual(session.render_window(slide=99), "density=semantic\n")
            self.assertIsNotNone(session.get_resource("image", "img1"))
            self.assertIsNotNone(session.get_resource("chart", "chart1"))
            self.assertIsNotNone(session.get_resource("table", "table1", rows="1-1"))
            with self.assertRaisesRegex(ValueError, "positive"):
                session.render_window(slide=0)
            with self.assertRaisesRegex(ValueError, "span"):
                session.render_window(slide=1, span=0)
            with self.assertRaisesRegex(ValueError, "singular"):
                session.get_resource("images", "img1")

        session = open_pptx(rich_deck_pptx())
        with self.assertRaisesRegex(RuntimeError, "context manager"):
            session.render()

    def test_read_session_closes_package_when_parse_fails(self) -> None:
        session = open_pptx(rich_deck_pptx())
        with (
            patch("pptx_llm_parser.api.PptxParser.parse", side_effect=RuntimeError("boom")),
            self.assertRaisesRegex(RuntimeError, "boom"),
        ):
            session.__enter__()
        self.assertIsNone(session._package_reader)


if __name__ == "__main__":
    unittest.main()
