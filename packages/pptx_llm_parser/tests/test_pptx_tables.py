"""Table shapes (graphicFrame → a:tbl) and plain tab-separated rendering."""

from __future__ import annotations

import unittest
from pathlib import Path

from _pptx_fixtures import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_xml_shapes,
    table_shape_xml,
)
from pptx_llm_parser import Density, parse_pptx
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parser import PptxParser


def _table_deck(rows: list[list[str]]) -> Path:
    entries = {
        "[Content_Types].xml": content_types_xml(1),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(table_shape_xml(rows)),
    }
    return make_pptx(entries)


class TableShapeTests(unittest.TestCase):
    def test_table_shape_rows(self) -> None:
        parsed = PptxParser().parse(_table_deck([["A", "B"], ["C", "D"]]), ParseOptions())
        shapes = parsed.slides[0]["shapes"]
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0]["type"], "table")
        self.assertEqual(shapes[0]["name"], "Table 3")
        self.assertEqual(shapes[0]["rows"], [["A", "B"], ["C", "D"]])

    def test_plain_table_tab_separated(self) -> None:
        text = parse_pptx(_table_deck([["A", "B"], ["C", "D"]]), density=Density.PLAIN)
        self.assertIn("A\tB\nC\tD", text)

    def test_plain_table_truncates_over_ten_rows(self) -> None:
        rows = [[f"r{i}", f"v{i}"] for i in range(12)]
        text = parse_pptx(_table_deck(rows), density=Density.PLAIN)
        self.assertIn("r0\tv0", text)
        self.assertIn("r9\tv9", text)
        self.assertNotIn("r10\tv10", text)
        self.assertIn("[Table truncated: 12 rows, 2 cols]", text)


if __name__ == "__main__":
    unittest.main()
