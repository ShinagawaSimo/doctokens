"""Golden output comparison for all three densities (UPDATE_GOLDEN=1 regenerates)."""

from __future__ import annotations

import unittest

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import Density, parse_pptx

from test_support.file_contract import assert_text_matches_golden, golden_root, output_path, write_text_result

GOLDEN_DIR = golden_root("pptx")

_DENSITY_FILES = {
    Density.SEMANTIC: "parsed.html",
    Density.STRUCTURAL: "structural.html",
    Density.PLAIN: "plain.txt",
}


class GoldenOutputTests(unittest.TestCase):
    def _check(self, density: Density, name: str) -> None:
        actual = output_path("pptx", "golden-output", name)
        write_text_result(parse_pptx(rich_deck_pptx(with_geometry=True), density=density), actual)
        golden_path = GOLDEN_DIR / name
        assert_text_matches_golden(actual, golden_path)

    def test_semantic_golden(self) -> None:
        self._check(Density.SEMANTIC, "parsed.html")

    def test_structural_golden(self) -> None:
        self._check(Density.STRUCTURAL, "structural.html")

    def test_plain_golden(self) -> None:
        self._check(Density.PLAIN, "plain.txt")


if __name__ == "__main__":
    unittest.main()
