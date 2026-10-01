"""Focused DOCX tests for the rewritten public boundary."""

from __future__ import annotations

import unittest
from pathlib import Path

from docx_llm_parser import DocxReadSession, ParseResult, open_docx, parse_docx

FIXTURE = Path(__file__).resolve().parents[3] / "test_support/fixtures/docx/docx-paragraph.docx"


class PublicApiV2Tests(unittest.TestCase):
    def test_parse_returns_result_with_report_and_text(self) -> None:
        result = parse_docx(FIXTURE)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.report.format, "docx")
        self.assertEqual(result.selection, {"kind": "all"})
        self.assertEqual(result.syntax_version, "doctokens-xml/1.0")
        self.assertEqual(result.media_type, "application/xml")

    def test_session_owns_reader_and_expires_cleanly(self) -> None:
        session = open_docx(FIXTURE)
        self.assertIsInstance(session, DocxReadSession)
        with session:
            plain = session.render(density="plain")
            self.assertEqual(plain.syntax_version, "doctokens-plain/1.0")
        with self.assertRaisesRegex(RuntimeError, "not open"):
            session.render()

    def test_unconsumed_iterator_expires_with_its_session(self) -> None:
        session = open_docx(FIXTURE)
        with session:
            chunks = session.iter_render()
        with self.assertRaisesRegex(RuntimeError, "not open"):
            next(chunks)


if __name__ == "__main__":
    unittest.main()
