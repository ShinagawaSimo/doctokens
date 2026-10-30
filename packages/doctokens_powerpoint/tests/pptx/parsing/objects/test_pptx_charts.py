"""A dangling chart relationship cannot be saved as a normal native chart."""

from __future__ import annotations

import unittest

from _pptx_objects import chart_shape_xml
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


def _missing_chart_deck() -> bytes:
    rel = (
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" '
        'Target="../charts/chart1.xml"/>'
    )
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(
            1,
            extra_defaults='<Override PartName="/ppt/charts/chart1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>',
        ),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(chart_shape_xml()),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(rel),
    }
    return make_pptx(entries)


class ChartShapeTests(unittest.TestCase):
    def test_missing_chart_part_degrades_with_warning(self) -> None:
        parsed = PptxParser().parse(_missing_chart_deck(), ParseOptions())
        self.assertTrue(any(w.code == "CHART_PART_MISSING" for w in parsed.warnings))
        text = parse_pptx(_missing_chart_deck(), density=Density.PLAIN).text
        self.assertIn("[Chart]", text)


if __name__ == "__main__":
    unittest.main()
