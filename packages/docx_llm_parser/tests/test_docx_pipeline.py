"""End-to-end parser tests using a generated DOCX package."""

from __future__ import annotations

import unittest

from _fixtures import write_rich_docx
from docx_llm_parser import (
    Density,
    get_resource,
    parse_docx,
    render_window,
)
from docx_llm_parser.core.enums import RevisionMode
from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.parser import DocxParser

from test_support.file_contract import output_path, source_path, write_text_result


class DocxPipelineTests(unittest.TestCase):
    def test_parse_render_query_write_and_batch_paths(self) -> None:
        docx_path = source_path("docx", "pipeline", "rich.docx")
        output_dir = output_path("docx", "pipeline", "parsed.html").parent
        write_rich_docx(docx_path)

        # Internal parse for structure assertions
        parsed = DocxParser().parse(
            docx_path,
            ParseOptions(
                revision_mode=RevisionMode.REVIEW,
            ),
        )

        self.assertEqual(parsed.metadata["sourceFile"], "rich.docx")
        self.assertEqual(parsed.package_info["entryCount"], 15)
        self.assertEqual(len(parsed.assets), 1)
        self.assertEqual(parsed.assets[0]["contentType"], "image/png")
        self.assertEqual(parsed.charts[0]["chartType"], "bar")
        self.assertEqual(parsed.smartarts[0]["layoutType"], "process")
        self.assertEqual(parsed.headers[0]["text"], "Header text")
        self.assertEqual(parsed.footers[0]["text"], "Footer text")
        self.assertEqual(parsed.footnotes[0]["text"], "Footnote text")
        self.assertEqual(parsed.endnotes[0]["text"], "Endnote text")
        self.assertEqual(parsed.comments[0]["author"], "Reviewer")
        self.assertIn("paragraphCount", parsed.metrics["counters"])

        # Public API: render
        html = parse_docx(docx_path, density=Density.SEMANTIC)
        self.assertIn("<h1><b><color value=#FF0000>Document Title</color>", html)
        self.assertIn("<a href=https://example.test>link</a>", html)
        self.assertIn("<chart id=chart1 type=bar", html)
        self.assertIn("<smartart id=smartart1 type=process nodes=2 links=1 truncated>", html)
        self.assertIn("<img id=img1", html)
        self.assertIn("<!-- supplemental -->", html)

        structural_html = parse_docx(docx_path, density=Density.STRUCTURAL)
        plain_text = parse_docx(docx_path, density=Density.PLAIN)
        self.assertIn("<chart id=chart1 type=bar", structural_html)
        self.assertIn("Footnote text", plain_text)
        self.assertIn("Last page", render_window(docx_path, page=-1))

        # structural: no headers/footers; notes and comments remain.
        self.assertNotIn("Header text", structural_html)
        self.assertNotIn("Footer text", structural_html)
        self.assertIn("<footnote id=", structural_html)
        self.assertIn("<comment id=", structural_html)

        # Plain density: headers/footers excluded, comments retained.
        self.assertNotIn("[Headers]", plain_text)
        self.assertNotIn("[Footers]", plain_text)
        self.assertNotIn("Header text", plain_text)
        self.assertIn("[Comments]", plain_text)
        self.assertIn("Comment text", plain_text)

        # Public API: resource extraction
        chart_html = get_resource(docx_path, "chart", "chart1")
        self.assertIsNotNone(chart_html)
        assert chart_html is not None
        self.assertIn("type=bar", chart_html)
        table_html = get_resource(docx_path, "table", "t1")
        self.assertIsNotNone(table_html)
        assert table_html is not None
        self.assertIn("rows=2", table_html)

        # Test-side atomic write; production APIs return text/iterators only.
        stale = output_dir / "readable.md"
        stale.write_text("keep", encoding="utf-8")
        html_path = write_text_result(html, output_path("docx", "pipeline", "parsed.html"))
        text_path = write_text_result(plain_text, output_path("docx", "pipeline", "plain.txt"))
        self.assertEqual(html_path.name, "parsed.html")
        self.assertEqual(text_path.name, "plain.txt")
        self.assertEqual(stale.read_text(encoding="utf-8"), "keep")
        self.assertEqual(list(output_dir.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
