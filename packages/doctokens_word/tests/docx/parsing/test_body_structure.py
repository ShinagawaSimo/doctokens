"""Body-level structure tests — content controls, unknown children, section breaks, numbering."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from _word_packages import _make_docx
from doctokens_word import parse_docx
from doctokens_word.docx.model import ParseOptions
from doctokens_word.docx.model.enums import Density
from doctokens_word.docx.parsing import get_render_pipeline
from doctokens_word.docx.parsing.runner import DocxParser

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


class BodyStructureTests(unittest.TestCase):
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
        self.assertEqual(_body_text_for_page("".join(get_render_pipeline(Density.STRUCTURAL).render(parsed))), ["Visible"])

    def test_empty_numbered_paragraph_keeps_label(self) -> None:
        """Word renders an empty numbered paragraph as its visible number; the label
        makes the paragraph non-empty, so it must be kept and the counter advanced."""
        data = _make_docx(
            '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr></w:p>'
            '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
            "<w:r><w:t>Item</w:t></w:r></w:p>",
            extra_entries={"word/numbering.xml": _NUMBERING_XML},
        )
        self.assertEqual(_body_text_for_page(parse_docx(data).text), ["1. ", "2. Item"])

    def test_full_level_override_honors_its_start_override_in_final_text(self) -> None:
        """A ``lvlOverride`` can replace formatting and independently restart its level."""
        numbering = f"""<w:numbering xmlns:w="{NS_W}">
          <w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0">
            <w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>
          </w:lvl></w:abstractNum>
          <w:num w:numId="1"><w:abstractNumId w:val="1"/><w:lvlOverride w:ilvl="0">
            <w:startOverride w:val="5"/><w:lvl w:ilvl="0"><w:numFmt w:val="upperRoman"/>
            <w:lvlText w:val="(%1)"/><w:suff w:val="space"/></w:lvl>
          </w:lvlOverride></w:num>
        </w:numbering>"""
        data = _make_docx(
            '<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Item</w:t></w:r></w:p>',
            extra_entries={"word/numbering.xml": numbering},
        )

        self.assertEqual(_body_text_for_page(parse_docx(data).text), ["(V) Item"])

    def test_hyperlink_without_relationship_degrades(self) -> None:
        """A dangling hyperlink r:id must not abort the whole parse."""
        data = _make_docx('<w:p><w:hyperlink r:id="rMissing"><w:r><w:t>link text</w:t></w:r></w:hyperlink></w:p>')
        parsed = DocxParser().parse(data, ParseOptions())
        self.assertEqual(_body_text_for_page("".join(get_render_pipeline(Density.STRUCTURAL).render(parsed))), ["link text"])
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
        root = ET.fromstring(parse_docx(data).text)
        self.assertEqual(len(root.findall(".//table")), 2)
        self.assertEqual(root.find(".//table/tr/td").get("rowspan"), "3")

    def test_window_on_page_hole_returns_empty(self) -> None:
        """Pages skipped by multiple breaks contain no blocks; window() must
        not fall back to the whole document."""
        data = _make_docx(
            "<w:p><w:r><w:t>Only page</w:t></w:r></w:p>"
            "<w:p><w:r><w:lastRenderedPageBreak/><w:lastRenderedPageBreak/><w:t>Page three</w:t></w:r></w:p>"
        )
        hole_window = parse_docx(data, page_hint=2).text
        self.assertNotIn("Only page", hole_window)
        self.assertNotIn("Page three", hole_window)
        last_window = parse_docx(data, page_hint=-1).text
        self.assertIn("Page three", last_window)

    def test_inline_rendered_page_break_splits_paragraph_and_windows(self) -> None:
        """A calculated break keeps the text on the page where Word rendered it."""
        data = _make_docx(
            "<w:p><w:r><w:t>A</w:t><w:lastRenderedPageBreak/><w:t>B</w:t>"
            "<w:lastRenderedPageBreak/><w:t>C</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>D</w:t></w:r></w:p>"
        )
        parsed = DocxParser().parse(data, ParseOptions())
        rendered = ET.fromstring("".join(get_render_pipeline(Density.SEMANTIC).render(parsed)))
        self.assertEqual([item.get("number") for item in rendered.findall(".//body/page")], ["1", "2", "3"])
        self.assertEqual([item.text for item in rendered.findall(".//body/p")], ["A", "B", "C", "D"])
        self.assertEqual(_body_text_for_page(parse_docx(data, page_hint=2).text), ["B"])
        self.assertEqual(_body_text_for_page(parse_docx(data, page_hint=3).text), ["C", "D"])

    def test_inline_rendered_page_breaks_without_runs(self) -> None:
        """The compact parse mode retains text page segments without run metadata."""
        data = _make_docx("<w:p><w:r><w:t>A</w:t><w:lastRenderedPageBreak/><w:t>B</w:t></w:r></w:p>")
        parsed = DocxParser().parse(data, ParseOptions(include_runs=False))
        self.assertEqual(_body_text_for_page("".join(get_render_pipeline(Density.STRUCTURAL).render(parsed))), ["A", "B"])

    def test_leading_inline_break_assigns_block_to_first_content_page(self) -> None:
        data = _make_docx("<w:p><w:r><w:lastRenderedPageBreak/><w:t>B</w:t></w:r></w:p>")
        parsed = DocxParser().parse(data, ParseOptions())
        root = ET.fromstring("".join(get_render_pipeline(Density.SEMANTIC).render(parsed)))
        self.assertEqual([item.get("number") for item in root.findall(".//body/page")], ["2"])
        self.assertEqual([item.text for item in root.findall(".//body//p")], ["B"])

    def test_table_cell_paragraph_keeps_inline_pages_and_advances_body(self) -> None:
        data = _make_docx(
            "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t><w:lastRenderedPageBreak/>"
            "<w:t>B</w:t><w:lastRenderedPageBreak/><w:t>C</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
            "<w:p><w:r><w:t>D</w:t></w:r></w:p>"
        )
        parsed = DocxParser().parse(data, ParseOptions())
        rendered = ET.fromstring("".join(get_render_pipeline(Density.SEMANTIC).render(parsed)))
        self.assertEqual([item.get("number") for item in rendered.findall(".//table//page")], ["2", "3"])
        self.assertEqual([item.text for item in rendered.findall(".//body/p")], ["D"])

    def test_navigation_citation(self) -> None:
        """Preserve the independent citation/navigation coverage of this case."""
        data = _make_docx(
            '<w:p><w:hyperlink w:anchor="target"><w:r><w:t>Jump</w:t></w:r></w:hyperlink></w:p>'
            '<w:p><w:bookmarkStart w:id="9" w:name="target"/>'
            '<w:fldSimple w:instr="CITATION Smith2024"><w:r><w:t>(Smith, 2024)</w:t></w:r></w:fldSimple></w:p>'
        )
        root = ET.fromstring(parse_docx(data, density=Density.SEMANTIC).text)
        citation = root.find(".//p[@anchor='target']/cite")
        assert citation is not None
        self.assertEqual((citation.get("key"), citation.text), ("Smith2024", "(Smith, 2024)"))


def _body_text_for_page(output: str) -> list[str]:
    root = ET.fromstring(output)
    return ["".join(item.itertext()) for item in root.findall(".//body//p")]


if __name__ == "__main__":
    unittest.main()
