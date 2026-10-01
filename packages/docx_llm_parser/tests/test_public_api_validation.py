"""Validation contracts for the DOCX v2 public API."""

from __future__ import annotations

import unittest
from pathlib import Path

from docx_llm_parser import open_docx, parse_docx
from docx_llm_parser.core.enums import RevisionMode
from docx_llm_parser.core.models import ParseOptions

FIXTURE = Path(__file__).resolve().parents[3] / "test_support/fixtures/docx/docx-paragraph.docx"


class PublicApiValidationTests(unittest.TestCase):
    def test_density_and_window_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "density"):
            parse_docx(FIXTURE, density="typo")
        with self.assertRaisesRegex(ValueError, "page_hint"):
            parse_docx(FIXTURE, page_hint=0)
        with self.assertRaisesRegex(ValueError, "span requires"):
            parse_docx(FIXTURE, span=2)

    def test_session_lifecycle_and_resources(self) -> None:
        with open_docx(FIXTURE) as session:
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
