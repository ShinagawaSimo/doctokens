"""Focused DOCX tests for the rewritten public boundary."""

from __future__ import annotations

import unittest

from doctokens_word import DocxReadSession, ParseResult, open_docx, parse_docx

from test_support.paths import REPO_ROOT

FIXTURE = REPO_ROOT / "test_support/fixtures/docx/docx-paragraph.docx"


class PublicApiV2Tests(unittest.TestCase):
    def test_density_projection_is_independent_of_read_history(self) -> None:
        # Session/cache infrastructure: ordinary content remains governed by
        # complete real-file goldens; no parallel content expectations are added.
        source = FIXTURE.with_name("docx-list-bullet-color.docx")
        fresh = {density: parse_docx(source, density=density) for density in ("plain", "structural", "semantic")}
        with open_docx(source) as session:
            for density in ("semantic", "structural", "plain", "semantic", "plain", "structural"):
                self.assertEqual(session.render(density=density).text, fresh[density].text)
                self.assertEqual("".join(session.iter_render(density=density)), fresh[density].text)

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
