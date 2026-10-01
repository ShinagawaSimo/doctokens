"""SmartArt shapes (graphicFrame → diagram data model) and plain placeholders."""

from __future__ import annotations

import unittest

from _pptx_fixtures import (
    content_types_xml,
    diagram_data_xml,
    diagram_layout_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
    smartart_shape_xml,
)
from pptx_llm_parser import parse_pptx
from pptx_llm_parser.core.enums import Density
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parsing.runner import PptxParser


def _smartart_deck(*, with_data: bool = True) -> bytes:
    rels = (
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData" '
        'Target="../diagrams/data1.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout" '
        'Target="../diagrams/layout1.xml"/>'
    )
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(
            1,
            extra_defaults='<Override PartName="/ppt/diagrams/data1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml"/>'
            '<Override PartName="/ppt/diagrams/layout1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramLayout+xml"/>',
        ),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(smartart_shape_xml()),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(rels),
        "ppt/diagrams/layout1.xml": diagram_layout_xml(),
    }
    if with_data:
        entries["ppt/diagrams/data1.xml"] = diagram_data_xml()
    return make_pptx(entries)


class SmartArtShapeTests(unittest.TestCase):
    def test_plain_smartart_placeholder(self) -> None:
        text = parse_pptx(_smartart_deck(), density=Density.PLAIN).text
        self.assertIn("[SmartArt: process, 3 nodes]", text)

    def test_missing_data_part_degrades_with_warning(self) -> None:
        parsed = PptxParser().parse(_smartart_deck(with_data=False), ParseOptions())
        self.assertTrue(any(w.code == "SMARTART_PART_MISSING" for w in parsed.warnings))
        text = parse_pptx(_smartart_deck(with_data=False), density=Density.PLAIN).text
        self.assertIn("[SmartArt]", text)


if __name__ == "__main__":
    unittest.main()
