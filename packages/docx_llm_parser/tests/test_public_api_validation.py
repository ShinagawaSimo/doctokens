"""Validation contracts for the DOCX v2 public API."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _fixtures import write_rich_docx
from docx_llm_parser import open_docx, parse_docx
from docx_llm_parser.core.enums import RevisionMode
from docx_llm_parser.core.models import ParseOptions


class PublicApiValidationTests(unittest.TestCase):
    def test_density_and_window_validation(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            write_rich_docx(path)
            with self.assertRaisesRegex(ValueError, "density"):
                parse_docx(path, density="typo")
            with self.assertRaisesRegex(ValueError, "page_hint"):
                parse_docx(path, page_hint=0)
            with self.assertRaisesRegex(ValueError, "span requires"):
                parse_docx(path, span=2)

    def test_session_lifecycle_and_resources(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test.docx"
            write_rich_docx(path)
            with open_docx(path) as session:
                self.assertEqual(session.report.format, "docx")
                self.assertTrue(list(session.iter_render(density="plain")))
                with self.assertRaises(KeyError):
                    session.read_resource("image", "missing")
                with self.assertRaises(ValueError):
                    session.render_resource("images", "img1")
            with self.assertRaisesRegex(RuntimeError, "not open"):
                session.render()

    def test_parse_options_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "revision_mode"):
            ParseOptions(revision_mode="typo")  # type: ignore[arg-type]
        self.assertIs(ParseOptions(revision_mode="review").revision_mode, RevisionMode.REVIEW)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "must be greater than zero"):
            ParseOptions(max_zip_entries=0)


if __name__ == "__main__":
    unittest.main()
