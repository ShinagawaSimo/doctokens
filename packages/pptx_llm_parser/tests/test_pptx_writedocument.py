"""write_document: density file names, content, atomic replacement."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import Density, parse_pptx, write_document


class WriteDocumentTests(unittest.TestCase):
    def test_file_names_follow_density(self) -> None:
        deck = rich_deck_pptx()
        with TemporaryDirectory() as temp_dir:
            out = Path(temp_dir) / "out"
            semantic = write_document(deck, out, density=Density.SEMANTIC)
            structural = write_document(deck, out, density=Density.STRUCTURAL)
            plain = write_document(deck, out, density=Density.PLAIN)
        self.assertEqual(semantic.name, "parsed.html")
        self.assertEqual(structural.name, "structural.html")
        self.assertEqual(plain.name, "plain.txt")

    def test_content_matches_parse_pptx(self) -> None:
        deck = rich_deck_pptx()
        with TemporaryDirectory() as temp_dir:
            out = Path(temp_dir)
            path = write_document(deck, out, density=Density.STRUCTURAL)
            content = path.read_text(encoding="utf-8")
        self.assertEqual(content, parse_pptx(deck, density=Density.STRUCTURAL))

    def test_atomic_write_keeps_stale_files_and_no_tmp_leftovers(self) -> None:
        deck = rich_deck_pptx()
        with TemporaryDirectory() as temp_dir:
            out = Path(temp_dir)
            stale = out / "readable.md"
            stale.write_text("keep", encoding="utf-8")
            path = write_document(deck, out, density=Density.PLAIN)
            self.assertEqual(stale.read_text(encoding="utf-8"), "keep")
            self.assertEqual(list(out.glob(".*.tmp")), [])
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
