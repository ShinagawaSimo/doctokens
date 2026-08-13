"""Golden output comparison for all three densities (UPDATE_GOLDEN=1 regenerates)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import Density, parse_pptx

GOLDEN_DIR = Path(__file__).parent / "golden"

_DENSITY_FILES = {
    Density.SEMANTIC: "parsed.html",
    Density.STRUCTURAL: "structural.html",
    Density.PLAIN: "plain.txt",
}


def _write_golden(name: str, content: str) -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    (GOLDEN_DIR / name).write_text(content, encoding="utf-8", newline="\n")


class GoldenOutputTests(unittest.TestCase):
    def _check(self, density: Density, name: str) -> None:
        text = parse_pptx(rich_deck_pptx(with_geometry=True), density=density)
        if os.environ.get("UPDATE_GOLDEN"):
            _write_golden(name, text)
        golden_path = GOLDEN_DIR / name
        self.assertEqual(text, golden_path.read_text(encoding="utf-8"))

    def test_semantic_golden(self) -> None:
        self._check(Density.SEMANTIC, "parsed.html")

    def test_structural_golden(self) -> None:
        self._check(Density.STRUCTURAL, "structural.html")

    def test_plain_golden(self) -> None:
        self._check(Density.PLAIN, "plain.txt")


if __name__ == "__main__":
    unittest.main()
