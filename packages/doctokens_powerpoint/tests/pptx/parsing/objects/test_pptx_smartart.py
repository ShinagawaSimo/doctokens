"""SmartArt shapes (graphicFrame → diagram data model) and plain placeholders."""

from __future__ import annotations

import unittest

from _pptx_objects import diagram_data_xml, diagram_layout_xml, smartart_shape_xml
from _pptx_package import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
)
from doctokens_powerpoint import parse_pptx
from doctokens_powerpoint.pptx.model.enums import Density
from doctokens_powerpoint.pptx.model.presentation import ParseOptions
from doctokens_powerpoint.pptx.parsing.runner import PptxParser


def _smartart_deck(*, with_data: bool = True, data_xml: str | None = None) -> bytes:
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
        entries["ppt/diagrams/data1.xml"] = data_xml if data_xml is not None else diagram_data_xml()
    return make_pptx(entries)


class SmartArtShapeTests(unittest.TestCase):
    def test_plain_smartart_placeholder(self) -> None:
        text = parse_pptx(_smartart_deck(), density=Density.PLAIN).text
        self.assertEqual(
            text,
            "density=plain format=pptx\n=== Slide 1 ===\n[SmartArt: process, 3 nodes]\n"
            "[1] Start\n[2] Middle\n[3] End\n[Link 1 -> 2]\n[Link 2 -> 3]",
        )

    def test_missing_data_part_degrades_with_warning(self) -> None:
        parsed = PptxParser().parse(_smartart_deck(with_data=False), ParseOptions())
        self.assertTrue(any(w.code == "SMARTART_PART_MISSING" for w in parsed.warnings))
        text = parse_pptx(_smartart_deck(with_data=False), density=Density.PLAIN).text
        self.assertIn("[SmartArt]", text)

    def test_out_of_order_duplicate_and_dangling_producer_records(self) -> None:
        # Duplicate modelIds, a dangling edge and a connection list before its
        # point list are malformed producer states Office cannot reliably save.
        xml = (
            '<dgm:dataModel xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<dgm:cxnLst><dgm:cxn srcId="A" destId="B" type="parOf"/>'
            '<dgm:cxn fromModelId="B" toModelId="R"/><dgm:cxn srcId="missing" destId="B"/></dgm:cxnLst>'
            '<dgm:ptLst><dgm:pt modelId="A"><dgm:t><a:t>A, first</a:t></dgm:t></dgm:pt>'
            '<dgm:pt modelId="B"><dgm:t><a:t>B</a:t></dgm:t></dgm:pt>'
            '<dgm:pt modelId="A"><dgm:t><a:t>Duplicate</a:t></dgm:t></dgm:pt>'
            '<dgm:pt modelId="R" type="doc"/></dgm:ptLst></dgm:dataModel>'
        )
        result = parse_pptx(_smartart_deck(data_xml=xml), density="structural")
        self.assertEqual(
            result.text,
            '<presentation density="structural" format="pptx"><slide number="1">'
            '<smartart id="smartart1" incomplete="true" links="2" nodes="4" shape-id="s1" type="process">'
            '<node id="1">A, first</node><node id="2">B</node><node id="3">Duplicate</node>'
            '<node id="4" kind="doc" /><link from="1" kind="parOf" to="2" /><link from="2" to="4" />'
            "</smartart></slide></presentation>",
        )
        self.assertEqual(
            [warning.code for warning in result.report.warnings],
            ["LAYOUT_PART_MISSING", "SMARTART_DUPLICATE_MODEL_ID", "SMARTART_UNRESOLVED_LINK"],
        )


if __name__ == "__main__":
    unittest.main()
