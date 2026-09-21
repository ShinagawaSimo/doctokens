"""Focused DOCX tests for the rewritten public boundary."""

from __future__ import annotations

import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from _fixtures import write_rich_docx
from docx_llm_parser import DocxReadSession, ParseResult, open_docx, parse_docx


class PublicApiV2Tests(unittest.TestCase):
    def test_parse_returns_result_with_report_and_text(self) -> None:
        path = Path("out/test-artifacts/inputs/docx/api-v2.docx")
        path.parent.mkdir(parents=True, exist_ok=True)
        write_rich_docx(path)
        result = parse_docx(path)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.report.format, "docx")
        self.assertIn("Document Title", result.text)
        self.assertEqual(result.selection, {"kind": "all"})
        self.assertEqual(result.syntax_version, "doctokens-xml/1.0")
        self.assertEqual(result.media_type, "application/xml")
        self.assertEqual(ET.fromstring(result.text).tag, "document")

    def test_session_owns_reader_and_expires_cleanly(self) -> None:
        path = Path("out/test-artifacts/inputs/docx/api-v2-session.docx")
        path.parent.mkdir(parents=True, exist_ok=True)
        write_rich_docx(path)
        session = open_docx(path)
        self.assertIsInstance(session, DocxReadSession)
        with session:
            self.assertIn("Last page", session.render(page_hint=-1).text)
            plain = session.render(density="plain", page_hint=2)
            self.assertEqual(plain.syntax_version, "doctokens-plain/1.0")
            self.assertIn("\n<page=2>\n", plain.text)
            self.assertTrue(session.read_resource("image", "img1"))
            with self.assertRaisesRegex(ValueError, "read_resource"):
                session.render_resource("image", "img1")
        with self.assertRaisesRegex(RuntimeError, "not open"):
            session.render()

    def test_unconsumed_iterator_expires_with_its_session(self) -> None:
        path = Path("out/test-artifacts/inputs/docx/api-v2-iterator.docx")
        path.parent.mkdir(parents=True, exist_ok=True)
        write_rich_docx(path)
        session = open_docx(path)
        with session:
            chunks = session.iter_render()
        with self.assertRaisesRegex(RuntimeError, "not open"):
            next(chunks)


if __name__ == "__main__":
    unittest.main()
