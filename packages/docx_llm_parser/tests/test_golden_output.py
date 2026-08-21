"""Golden output tests — freeze HTML and debug JSON to catch unintended changes."""

import unittest
from pathlib import Path

from _fixtures import write_rich_docx
from docx_llm_parser import Density, parse_docx
from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.parser import DocxParser

from test_support.file_contract import (
    assert_json_matches_golden,
    assert_text_matches_golden,
    golden_root,
    output_path,
    source_path,
    write_text_result,
)

GOLDEN_DIR = golden_root("docx")
_EXCLUDE_DEBUG = {"metrics.json"}


class GoldenOutputTests(unittest.TestCase):
    def test_semantic_output_matches_golden(self) -> None:
        actual = _render_density(Density.SEMANTIC)
        assert_text_matches_golden(actual, GOLDEN_DIR / "parsed.html")

    def test_structural_output_matches_golden(self) -> None:
        actual = _render_density(Density.STRUCTURAL)
        assert_text_matches_golden(actual, GOLDEN_DIR / "structural.html")

    def test_plain_output_matches_golden(self) -> None:
        actual = _render_density(Density.PLAIN)
        assert_text_matches_golden(actual, GOLDEN_DIR / "plain.txt")

    def test_debug_artifacts_match_golden(self) -> None:
        docx_path = source_path("docx", "golden-debug", "rich.docx")
        output_dir = output_path("docx", "golden-debug", "parsed.html").parent
        write_rich_docx(docx_path)
        DocxParser().parse(docx_path, ParseOptions(debug=True, output_dir=output_dir))
        debug_dir = output_dir / ".debug"

        for json_file in sorted(debug_dir.glob("*.json")):
            assert_json_matches_golden(json_file, GOLDEN_DIR / json_file.name, exclude=_EXCLUDE_DEBUG)


def _render_density(density: Density) -> Path:
    docx_path = source_path("docx", "golden-output", "rich.docx")
    output_name = {
        Density.SEMANTIC: "parsed.html",
        Density.STRUCTURAL: "structural.html",
        Density.PLAIN: "plain.txt",
    }[density]
    actual = output_path("docx", "golden-output", output_name)
    write_rich_docx(docx_path)
    write_text_result(parse_docx(docx_path, density=density), actual)
    return actual


if __name__ == "__main__":
    unittest.main()
