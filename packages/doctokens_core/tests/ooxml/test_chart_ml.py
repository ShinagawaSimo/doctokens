"""Invalid values and incomplete chart parts are exceptional producer input."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from doctokens_core.ooxml.charts.parser import ChartParser
from doctokens_core.ooxml.charts.preview import append_chart_preview
from doctokens_core.ooxml.charts.values import (
    _first_dimension,
    _namespace,
    _safe_int,
    _summary_chart_type,
    _true_value,
)
from doctokens_core.output.xml import element, serialize


class ChartParserTests(unittest.TestCase):
    def test_duplicate_and_dangling_axis_ids_do_not_create_false_links(self) -> None:
        # Normal Office cannot save duplicated axis declarations or dangling
        # cross-axis/plot references. Preserve axes without guessing ownership.
        source = ET.fromstring(
            '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:chart><c:plotArea>'
            '<c:barChart><c:axId val="7"/><c:axId val="99"/></c:barChart>'
            '<c:catAx><c:axId val="7"/><c:crossAx val="99"/></c:catAx>'
            '<c:valAx><c:axId val="7"/><c:crossAx val="7"/></c:valAx>'
            "</c:plotArea></c:chart></c:chartSpace>"
        )
        node = element("document", density="semantic", format="docx")
        append_chart_preview(node, ChartParser().parse(source))
        self.assertEqual(
            serialize(node),
            '<document density="semantic" format="docx" points="0" series="0"><axis id="axis1" kind="catAx" />'
            '<axis id="axis2" kind="valAx" /><plot index="1" type="bar" /></document>',
        )

    def test_chart_helpers_and_empty_chart_paths(self) -> None:
        self.assertEqual(ChartParser().parse(ET.Element("chartSpace"))["chart_type"], "unknown")
        self.assertEqual(_summary_chart_type([]), "unknown")
        self.assertIsNone(_safe_int("bad"))
        self.assertFalse(_true_value(None))
        self.assertIsNone(_namespace("plain"))
        self.assertEqual(_first_dimension({}), [])


if __name__ == "__main__":
    unittest.main()
