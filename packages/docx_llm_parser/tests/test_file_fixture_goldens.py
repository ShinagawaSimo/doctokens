"""Regression checks for manually authored DOCX fixture files."""

from __future__ import annotations

import json
import unittest

from docx_llm_parser import Density, parse_docx

from test_support.file_contract import fixture_root

_TEST_SUPPORT_ROOT = fixture_root().parent
_MATRIX_PATH = _TEST_SUPPORT_ROOT / "fixture_matrix.json"
_DENSITIES = {
    "semantic.html": Density.SEMANTIC,
    "structural.html": Density.STRUCTURAL,
    "plain.txt": Density.PLAIN,
}


class FileFixtureGoldenTests(unittest.TestCase):
    def test_available_docx_fixtures_match_their_goldens(self) -> None:
        """Every checked-in DOCX fixture in the matrix has stable output at each density."""
        matrix = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))

        for case in matrix["packages"]["docx"]:
            fixture = _TEST_SUPPORT_ROOT / case["fixture"]
            if not fixture.exists():
                continue
            for golden_name in case["golden"]:
                golden = _TEST_SUPPORT_ROOT / golden_name
                density_name = next(name for name in _DENSITIES if golden.name.endswith(name))
                with self.subTest(fixture=fixture.name, density=density_name):
                    self.assertTrue(golden.exists(), f"Missing golden: {golden}")
                    self.assertEqual(
                        parse_docx(fixture, density=_DENSITIES[density_name]),
                        golden.read_text(encoding="utf-8"),
                    )


if __name__ == "__main__":
    unittest.main()
