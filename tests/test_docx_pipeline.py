"""End-to-end parser tests using a generated DOCX package."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from docx_llm_parser import (
    Density,
    ParseOptions,
    RevisionMode,
    build_manifest,
    get_resource,
    list_resources,
    parse_docx,
    render_document,
    render_window,
)
from docx_llm_parser.api import write_document
from docx_llm_parser.concurrency import parse_many

from _fixtures import write_rich_docx


class DocxPipelineTests(unittest.TestCase):
    def test_parse_render_query_write_and_batch_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            docx_path = temp / "rich.docx"
            output_dir = temp / "out"
            write_rich_docx(docx_path)

            parsed = parse_docx(
                docx_path,
                ParseOptions(
                    debug=True,
                    output_dir=output_dir,
                    revision_mode=RevisionMode.REVIEW,
                ),
            )

            self.assertEqual(parsed.metadata["sourceFile"], "rich.docx")
            self.assertEqual(parsed.package_info["entryCount"], 15)
            self.assertTrue((output_dir / ".debug" / "blocks.json").exists())
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

            html = render_document(parsed, density=Density.SEMANTIC)
            self.assertIn("<h1>Document Title", html)
            self.assertIn("<a href=https://example.test>link</a>", html)
            self.assertIn("<chart id=chart1 type=bar", html)
            self.assertIn("<smartart id=smartart1 type=process nodes=2 links=1 truncated>", html)
            self.assertIn("<img id=img1", html)
            self.assertIn("<!-- supplemental -->", html)

            l1 = render_document(parsed, density=Density.STRUCTURAL)
            l0 = render_document(parsed, density=Density.PLAIN)
            self.assertIn("<chart id=chart1 type=bar", l1)
            self.assertIn("Footnote text", l0)
            self.assertIn("Last page", render_window(parsed, page=-1))

            manifest = build_manifest(parsed)
            self.assertGreaterEqual(manifest["pages"], 2)
            self.assertEqual(manifest["tables"], 1)
            self.assertEqual(manifest["images"], 1)
            self.assertEqual(len(list_resources(parsed, "images")), 1)
            self.assertEqual(get_resource(parsed, "chart", "chart1")["chartType"], "bar")
            table = get_resource(parsed, "table", "t1")
            self.assertIsNotNone(table)
            assert table is not None
            self.assertEqual(table["rowCount"], 2)

            stale = output_dir / "readable.md"
            stale.write_text("keep", encoding="utf-8")
            html_path = write_document(parsed, output_dir, density=Density.SEMANTIC)
            text_path = write_document(parsed, output_dir, density=Density.PLAIN)
            self.assertEqual(html_path.name, "parsed.html")
            self.assertEqual(text_path.name, "l0.txt")
            self.assertEqual(stale.read_text(encoding="utf-8"), "keep")
            self.assertEqual(list(output_dir.glob(".*.tmp")), [])

            results = parse_many(
                [docx_path, temp / "missing.docx"],
                temp / "batch",
                max_workers=1,
                revision_mode="final",
            )
            self.assertTrue(results[0].ok)
            self.assertFalse(results[1].ok)
            self.assertIn("FileNotFoundError", results[1].error or "")


if __name__ == "__main__":
    unittest.main()
