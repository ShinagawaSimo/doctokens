"""Golden output tests for the public render contract."""

import unittest
from pathlib import Path

from _fixtures import write_rich_docx

from test_support.api_v2_text import Density, parse_docx
from test_support.file_contract import (
    assert_text_matches_golden,
    golden_root,
    output_path,
    source_path,
    write_text_result,
)

GOLDEN_DIR = golden_root("docx")


class GoldenOutputTests(unittest.TestCase):
    def test_semantic_output_matches_golden(self) -> None:
        actual = _render_density(Density.SEMANTIC)
        assert_text_matches_golden(actual, GOLDEN_DIR / "parsed.xml")

    def test_structural_output_matches_golden(self) -> None:
        actual = _render_density(Density.STRUCTURAL)
        assert_text_matches_golden(actual, GOLDEN_DIR / "structural.xml")

    def test_plain_output_matches_golden(self) -> None:
        actual = _render_density(Density.PLAIN)
        assert_text_matches_golden(actual, GOLDEN_DIR / "plain.txt")


def _render_density(density: Density) -> Path:
    docx_path = source_path("docx", "golden-output", "rich.docx")
    output_name = {
        Density.SEMANTIC: "parsed.xml",
        Density.STRUCTURAL: "structural.xml",
        Density.PLAIN: "plain.txt",
    }[density]
    actual = output_path("docx", "golden-output", output_name)
    write_rich_docx(docx_path)
    write_text_result(parse_docx(docx_path, density=density), actual)
    return actual


if __name__ == "__main__":
    unittest.main()
