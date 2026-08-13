"""get_resource: lazy image/media bytes, full chart/smartart/table records."""

from __future__ import annotations

import unittest

from _pptx_fixtures import (
    PNG_BYTES,
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    rich_deck_pptx,
    root_rels_xml,
    slide_xml_shapes,
    table_shape_xml,
)
from pptx_llm_parser import get_resource


def _numeric_table_deck() -> bytes:
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(table_shape_xml([["1", "2"], ["3", "x"]])),
    }
    return make_pptx(entries)


class GetResourceTests(unittest.TestCase):
    def test_image_returns_base64(self) -> None:
        data = get_resource(rich_deck_pptx(), "image", "img1")
        self.assertEqual(data, PNG_BYTES)

    def test_media_returns_base64(self) -> None:
        data = get_resource(rich_deck_pptx(), "media", "media1")
        self.assertEqual(data, "")

    def test_chart_full_series(self) -> None:
        data = get_resource(rich_deck_pptx(), "chart", "chart1")
        self.assertEqual(
            data,
            "<chart id=chart1 type=bar title=Sales series=2 points=4>\n"
            "<series id=1 name=Q1 categories=East,West values=10,20 min=10 max=20>\n"
            "<series id=2 name=Q2 categories=East,West values=15,25 min=15 max=25>",
        )

    def test_smartart_full_record(self) -> None:
        data = get_resource(rich_deck_pptx(), "smartart", "smartart1")
        self.assertEqual(
            data,
            "<smartart id=smartart1 type=process nodes=3 links=2>\n"
            "<node id=1>Start\n"
            "<node id=2>Middle\n"
            "<node id=3>End\n"
            "<link from=1 to=2>\n"
            "<link from=2 to=3>",
        )

    def test_table_full_render(self) -> None:
        data = get_resource(rich_deck_pptx(), "table", "table1")
        self.assertEqual(data, "<table id=table1 rows=2 cols=2>\n<tr><td>A</td><td>B</td>\n<tr><td>C</td><td>D</td>")

    def test_table_rows_slice_and_columns_filter(self) -> None:
        data = get_resource(rich_deck_pptx(), "table", "table1", rows="1-1", columns=[1])
        self.assertEqual(data, "<table id=table1 rows=1 cols=1>\n<tr><td>B</td>")

    def test_table_aggregate_sum(self) -> None:
        data = get_resource(_numeric_table_deck(), "table", "table1", aggregate="sum", aggregate_column=0)
        self.assertIn("<aggregate op=sum column=0 value=4>", data)

    def test_table_aggregate_count_counts_numeric_cells(self) -> None:
        data = get_resource(_numeric_table_deck(), "table", "table1", aggregate="count", aggregate_column=1)
        self.assertIn("<aggregate op=count column=1 value=1>", data)

    def test_table_unknown_aggregate_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "aggregate"):
            get_resource(_numeric_table_deck(), "table", "table1", aggregate="median", aggregate_column=0)

    def test_plural_type_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "singular"):
            get_resource(rich_deck_pptx(), "images", "img1")

    def test_unknown_type_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown resource type"):
            get_resource(rich_deck_pptx(), "unknown", "x")

    def test_missing_id_returns_none(self) -> None:
        self.assertIsNone(get_resource(rich_deck_pptx(), "image", "img99"))
        self.assertIsNone(get_resource(rich_deck_pptx(), "chart", "chart99"))


if __name__ == "__main__":
    unittest.main()
