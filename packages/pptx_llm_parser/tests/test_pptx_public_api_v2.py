"""Focused PPTX tests for the rewritten public boundary."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from _pptx_fixtures import rich_deck_pptx
from pptx_llm_parser import ParseResult, open_pptx, parse_pptx


class PublicApiV2Tests(unittest.TestCase):
    def test_parse_result_and_session_resource_lifecycle(self) -> None:
        source = rich_deck_pptx()
        result = parse_pptx(source)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.report.format, "pptx")
        self.assertEqual(result.syntax_version, "doctokens-xml/1.0")
        self.assertEqual(result.media_type, "application/xml")
        self.assertEqual(ET.fromstring(result.text).tag, "presentation")
        self.assertTrue(result.resources)
        with open_pptx(source) as session:
            self.assertEqual(session.render(slide=1).selection["kind"], "slide")
            self.assertTrue(session.read_resource("image", "img1"))
            with self.assertRaisesRegex(ValueError, "read_resource"):
                session.render_resource("image", "img1")
        with self.assertRaisesRegex(RuntimeError, "not open"):
            session.render()


if __name__ == "__main__":
    unittest.main()
