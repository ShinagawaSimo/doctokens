"""Golden output tests — freeze HTML and debug JSON to catch unintended changes."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from docx_llm_parser import Density, render_document
from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.core.enums import RevisionMode
from docx_llm_parser.parser import DocxParser

from _fixtures import write_rich_docx

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
_EXCLUDE_DEBUG = {"metrics.json"}


class GoldenOutputTests(unittest.TestCase):
    def test_semantic_output_matches_golden(self) -> None:
        html = _render_density(Density.SEMANTIC)
        golden_path = GOLDEN_DIR / "parsed.html"
        if os.environ.get("UPDATE_GOLDEN"):
            _write_golden(golden_path, html)
        expected = _read_golden(golden_path)
        self.assertEqual(expected, html, f"semantic output changed; see {golden_path}")

    def test_structural_output_matches_golden(self) -> None:
        html = _render_density(Density.STRUCTURAL)
        golden_path = GOLDEN_DIR / "l1.html"
        if os.environ.get("UPDATE_GOLDEN"):
            _write_golden(golden_path, html)
        expected = _read_golden(golden_path)
        self.assertEqual(expected, html, f"structural output changed; see {golden_path}")

    def test_plain_output_matches_golden(self) -> None:
        text = _render_density(Density.PLAIN)
        golden_path = GOLDEN_DIR / "l0.txt"
        if os.environ.get("UPDATE_GOLDEN"):
            _write_golden(golden_path, text)
        expected = _read_golden(golden_path)
        self.assertEqual(expected, text, f"plain output changed; see {golden_path}")

    def test_debug_artifacts_match_golden(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            docx_path = temp / "rich.docx"
            output_dir = temp / "out"
            write_rich_docx(docx_path)
            DocxParser().parse(docx_path, ParseOptions(debug=True, output_dir=output_dir))
            debug_dir = output_dir / ".debug"

            for json_file in sorted(debug_dir.glob("*.json")):
                name = json_file.name
                if name in _EXCLUDE_DEBUG:
                    continue
                actual_text = json_file.read_text(encoding="utf-8")
                # Normalize JSON for stable comparison
                actual = json.loads(actual_text)
                actual_normalized = json.dumps(actual, ensure_ascii=False, sort_keys=True)

                golden_path = GOLDEN_DIR / name
                if os.environ.get("UPDATE_GOLDEN"):
                    _write_golden(golden_path, actual_normalized)

                expected = _read_golden(golden_path)
                self.assertEqual(
                    expected,
                    actual_normalized,
                    f"debug artifact {name} changed; see {golden_path}",
                )


def _render_density(density: Density) -> str:
    with TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        docx_path = temp / "rich.docx"
        write_rich_docx(docx_path)
        return render_document(docx_path, density=density)


def _read_golden(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write_golden(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
