"""Body-level structure tests — content controls, unknown children, section breaks, numbering."""

from __future__ import annotations

import io
import unittest
import zipfile

from docx_llm_parser import render_window
from docx_llm_parser.core.enums import RevisionMode
from docx_llm_parser.core.models import ParseOptions
from docx_llm_parser.parser import DocxParser

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"

_NUMBERING_XML = f"""<w:numbering xmlns:w="{NS_W}">
  <w:abstractNum w:abstractNumId="1">
    <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/><w:suff w:val="space"/>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""


def _make_docx(body_xml: str, extra_entries: dict[str, str] | None = None) -> bytes:
    """Build a minimal DOCX whose body contains *body_xml*."""
    entries: dict[str, str] = {
        "[Content_Types].xml": (
            f'<Types xmlns="{NS_CT}">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'<Relationships xmlns="{NS_PKG_REL}">'
            f'<Relationship Id="r1" Type="{NS_R}/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": (
            f'<w:document xmlns:w="{NS_W}" xmlns:r="{NS_R}"><w:body>{body_xml}<w:sectPr/></w:body></w:document>'
        ),
        "word/_rels/document.xml.rels": f'<Relationships xmlns="{NS_PKG_REL}"/>',
    }
    if extra_entries:
        entries.update(extra_entries)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class BodyStructureTests(unittest.TestCase):
    def test_sdt_wrapped_content_parsed(self) -> None:
        """Content controls wrapping the whole body must not hide paragraphs/tables."""
        data = _make_docx(
            "<w:sdt><w:sdtContent>"
            "<w:p><w:r><w:t>Wrapped text</w:t></w:r></w:p>"
            "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
            "</w:sdtContent></w:sdt>"
        )
        parsed = DocxParser().parse(data, ParseOptions())
        self.assertEqual(parsed.blocks[0]["text"], "Wrapped text")
        self.assertEqual(parsed.blocks[1]["type"], "table")
        self.assertEqual(parsed.blocks[1]["rows"][0]["cells"][0]["text"], "Cell")

    def test_unknown_body_child_warns(self) -> None:
        """Content-bearing wrappers we do not support are surfaced as warnings."""
        data = _make_docx(
            "<w:customXml><w:p><w:r><w:t>Hidden</w:t></w:r></w:p></w:customXml>"
            '<w:p><w:bookmarkStart w:id="1" w:name="bm"/><w:r><w:t>Visible</w:t></w:r></w:p>'
        )
        parsed = DocxParser().parse(data, ParseOptions())
        codes = [warning.code for warning in parsed.warnings if warning.code == "UNSUPPORTED_BODY_CHILD"]
        self.assertEqual(codes, ["UNSUPPORTED_BODY_CHILD"])
        # Bookmarks are noise, not content: no warning, and the paragraph text survives.
        self.assertEqual(parsed.blocks[0]["text"], "Visible")

    def test_paragraph_sectpr_advances_page_after_paragraph(self) -> None:
        """A sectPr inside pPr starts the next block on a new page."""
        data = _make_docx(
            "<w:p><w:r><w:t>First</w:t></w:r></w:p>"
            "<w:p><w:pPr><w:sectPr/></w:pPr><w:r><w:t>Last of section</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Next section</w:t></w:r></w:p>"
        )
        parsed = DocxParser().parse(data, ParseOptions())
        self.assertEqual([block["page"] for block in parsed.blocks], [1, 1, 2])

    def test_empty_paragraph_sectpr_still_breaks_page(self) -> None:
        """Even a dropped empty paragraph's sectPr must start a new page."""
        data = _make_docx(
            "<w:p><w:r><w:t>A</w:t></w:r></w:p><w:p><w:pPr><w:sectPr/></w:pPr></w:p><w:p><w:r><w:t>B</w:t></w:r></w:p>"
        )
        parsed = DocxParser().parse(data, ParseOptions())
        self.assertEqual([block["page"] for block in parsed.blocks], [1, 2])

    def test_empty_numbered_paragraph_keeps_label(self) -> None:
        """Word renders an empty numbered paragraph as its visible number; the label
        makes the paragraph non-empty, so it must be kept and the counter advanced."""
        data = _make_docx(
            '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr></w:p>'
            '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
            "<w:r><w:t>Item</w:t></w:r></w:p>",
            extra_entries={"word/numbering.xml": _NUMBERING_XML},
        )
        parsed = DocxParser().parse(data, ParseOptions())
        texts = [block["text"] for block in parsed.blocks]
        self.assertEqual(texts, ["1. ", "2. Item"])

    def test_hyperlink_without_relationship_degrades(self) -> None:
        """A dangling hyperlink r:id must not abort the whole parse."""
        data = _make_docx('<w:p><w:hyperlink r:id="rMissing"><w:r><w:t>link text</w:t></w:r></w:hyperlink></w:p>')
        parsed = DocxParser().parse(data, ParseOptions())
        self.assertEqual(parsed.blocks[0]["text"], "link text")
        self.assertTrue(any(w.code == "HYPERLINK_TARGET_MISSING" for w in parsed.warnings))

    def test_table_page_split_preserves_vertical_merge(self) -> None:
        """A vMerge restart before a page break keeps accumulating rowSpan
        across the page-separated table segments."""
        data = _make_docx(
            "<w:tbl>"
            '<w:tr><w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr>'
            "<w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc></w:tr>"
            "<w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr>"
            "<w:p><w:r><w:lastRenderedPageBreak/><w:t>B</w:t></w:r></w:p></w:tc></w:tr>"
            "<w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr>"
            "<w:p><w:r><w:t>C</w:t></w:r></w:p></w:tc></w:tr>"
            "</w:tbl>"
        )
        parsed = DocxParser().parse(data, ParseOptions())
        tables = [block for block in parsed.blocks if block["type"] == "table"]
        self.assertEqual(len(tables), 2)
        # The origin in segment 1 spans all three rows, including segment 2's continues.
        self.assertEqual(tables[0]["rows"][0]["cells"][0]["rowSpan"], 3)
        self.assertEqual(tables[1]["rows"][0]["cells"][0]["vMerge"], "continue")

    def test_window_on_page_hole_returns_empty(self) -> None:
        """Pages skipped by multiple breaks contain no blocks; window() must
        not fall back to the whole document."""
        data = _make_docx(
            "<w:p><w:r><w:t>Only page</w:t></w:r></w:p>"
            "<w:p><w:r><w:lastRenderedPageBreak/><w:lastRenderedPageBreak/><w:t>Page three</w:t></w:r></w:p>"
        )
        hole_window = render_window(data, page=2)
        self.assertNotIn("Only page", hole_window)
        self.assertNotIn("Page three", hole_window)
        last_window = render_window(data, page=-1)
        self.assertIn("Page three", last_window)

    def test_revision_mode_original(self) -> None:
        data = _make_docx(
            "<w:p><w:r><w:t>base </w:t></w:r>"
            "<w:ins><w:r><w:t>inserted</w:t></w:r></w:ins>"
            "<w:del><w:r><w:delText>deleted</w:delText></w:r></w:del></w:p>"
        )
        original = DocxParser().parse(data, ParseOptions(revision_mode=RevisionMode.ORIGINAL))
        text = original.blocks[0]["text"]
        self.assertIn("deleted", text)
        self.assertNotIn("inserted", text)

        final = DocxParser().parse(data, ParseOptions(revision_mode=RevisionMode.FINAL))
        final_text = final.blocks[0]["text"]
        self.assertIn("inserted", final_text)
        self.assertNotIn("deleted", final_text)


if __name__ == "__main__":
    unittest.main()
