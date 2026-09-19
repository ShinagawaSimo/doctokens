"""Test-side output materialization for PPTX render results."""

from __future__ import annotations

import unittest

from _pptx_fixtures import rich_deck_pptx

from test_support.api_v2_text import Density, parse_pptx
from test_support.file_contract import output_path, write_text_result


class TestOutputMaterializationTests(unittest.TestCase):
    def test_file_names_follow_density(self) -> None:
        deck = rich_deck_pptx()
        semantic = write_text_result(
            parse_pptx(deck, density=Density.SEMANTIC),
            output_path("pptx", "write-document", "parsed.html"),
        )
        structural = write_text_result(
            parse_pptx(deck, density=Density.STRUCTURAL),
            output_path("pptx", "write-document", "structural.html"),
        )
        plain = write_text_result(
            parse_pptx(deck, density=Density.PLAIN),
            output_path("pptx", "write-document", "plain.txt"),
        )
        self.assertEqual(semantic.name, "parsed.html")
        self.assertEqual(structural.name, "structural.html")
        self.assertEqual(plain.name, "plain.txt")

    def test_content_matches_parse_pptx(self) -> None:
        deck = rich_deck_pptx()
        path = write_text_result(
            parse_pptx(deck, density=Density.STRUCTURAL),
            output_path("pptx", "write-document", "structural.html"),
        )
        content = path.read_text(encoding="utf-8")
        self.assertEqual(content, parse_pptx(deck, density=Density.STRUCTURAL))

    def test_atomic_write_keeps_stale_files_and_no_tmp_leftovers(self) -> None:
        deck = rich_deck_pptx()
        out = output_path("pptx", "write-document", "plain.txt").parent
        stale = out / "readable.md"
        stale.write_text("keep", encoding="utf-8")
        path = write_text_result(parse_pptx(deck, density=Density.PLAIN), out / "plain.txt")
        self.assertEqual(stale.read_text(encoding="utf-8"), "keep")
        self.assertEqual(list(out.glob(".*.tmp")), [])
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
