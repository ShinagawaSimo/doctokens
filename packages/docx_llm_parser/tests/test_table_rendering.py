"""Regression tests for stable table identity and truncation."""

from __future__ import annotations

import unittest
from typing import Any, cast
from xml.etree import ElementTree as ET

from docx_llm_parser.core.models import ParsedDocument, ParseOptions, ParseWarning
from docx_llm_parser.core.package import PackageReader
from docx_llm_parser.core.relationships import RelationshipIndex
from docx_llm_parser.extractors.body import DocumentBodyParser
from docx_llm_parser.ooxml.numbering import NumberingMap, NumberingState
from docx_llm_parser.ooxml.styles import StyleMap
from docx_llm_parser.renderers.html5 import manifest as _manifest
from docx_llm_parser.renderers.html5 import render_resource as _render_resource
from docx_llm_parser.renderers.plain.helpers import table_text_only
from docx_llm_parser.renderers.tables.render import table_id

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _table_xml(body: str) -> ET.Element:
    return ET.fromstring(f'<w:tbl xmlns:w="{WORD_NS}">{body}</w:tbl>')


def _body_parser() -> DocumentBodyParser:
    warnings: list[ParseWarning] = []
    numbering = NumberingMap({}, {}, warnings)
    return DocumentBodyParser(
        cast(PackageReader, object()),
        StyleMap({}, warnings),
        ParseOptions(),
        warnings,
        RelationshipIndex.from_records([]),
        {},
        {},
        NumberingState(numbering, warnings),
    )


class TableIdentityTests(unittest.TestCase):
    def test_logical_tables_receive_unique_ids(self) -> None:
        parser = _body_parser()
        first = parser.parse_table(
            _table_xml("<w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc></w:tr>"),
            "word/document.xml",
        )
        second = parser.parse_table(
            _table_xml("<w:tr><w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr>"),
            "word/document.xml",
        )

        self.assertEqual((first[0]["tableId"], first[0]["segmentIndex"]), ("t1", 1))
        self.assertEqual((second[0]["tableId"], second[0]["segmentIndex"]), ("t2", 1))
        self.assertEqual(table_id(first[0]), "t1")

    def test_page_split_segments_share_logical_table_id(self) -> None:
        parser = _body_parser()
        table = _table_xml(
            "<w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc></w:tr>"
            "<w:tr><w:tc><w:p><w:r><w:lastRenderedPageBreak/><w:t>B</w:t>"
            "</w:r></w:p></w:tc></w:tr>"
        )

        segments = parser.parse_table(table, "word/document.xml")

        self.assertEqual(
            [(block["tableId"], block["segmentIndex"]) for block in segments],
            [("t1", 1), ("t1", 2)],
        )

    def test_plain_truncation_uses_assigned_table_id(self) -> None:
        rows: list[dict[str, Any]] = [{"cells": [{"text": "x"}]} for _ in range(11)]

        rendered = table_text_only(cast(Any, {"type": "table", "tableId": "t7", "rows": rows, "columnCount": 1}))

        self.assertIn("[Table truncated: 11 rows, 1 cols]", rendered)

    def test_table_resource_reassembles_page_segments(self) -> None:
        segments = [
            {
                "id": "b1",
                "type": "table",
                "part": "word/document.xml",
                "order": 1,
                "page": 1,
                "tableId": "t1",
                "segmentIndex": 1,
                "rows": [{"rowIndex": 0, "cells": []}],
                "columnCount": 2,
            },
            {
                "id": "b2",
                "type": "table",
                "part": "word/document.xml",
                "order": 1,
                "page": 2,
                "tableId": "t1",
                "segmentIndex": 2,
                "rows": [{"rowIndex": 1, "cells": []}],
                "columnCount": 3,
            },
        ]
        parsed = ParsedDocument(
            metadata={},
            package_info={},
            blocks=cast(Any, segments),
            relationships=[],
            styles=[],
            warnings=[],
        )

        tables_html = _render_resource(parsed, "tables")
        self.assertEqual(len(tables_html), 1)
        self.assertIn("id=t1", tables_html[0])
        self.assertIn("rows=2", tables_html[0])
        self.assertIn("cols=3", tables_html[0])

        results = _render_resource(parsed, "table", "t1")
        self.assertEqual(len(results), 1)
        self.assertIn("<table id=t1 rows=2 cols=3>", results[0])
        self.assertEqual(_manifest(parsed)["tables"], 1)

    def _make_table(self, headers: list[str], data: list[list[str]], table_id: str = "t1") -> ParsedDocument:
        """Build a minimal ParsedDocument with one table."""
        header_row = {
            "rowIndex": 0,
            "isHeader": True,
            "cells": [
                {"rowIndex": 0, "colIndex": i, "rowSpan": 1, "colSpan": 1, "text": h, "blocks": []} for i, h in enumerate(headers)
            ],
        }
        data_rows = [
            {
                "rowIndex": i + 1,
                "isHeader": False,
                "cells": [
                    {
                        "rowIndex": i + 1,
                        "colIndex": j,
                        "rowSpan": 1,
                        "colSpan": 1,
                        "text": v,
                        "blocks": [],
                    }
                    for j, v in enumerate(row)
                ],
            }
            for i, row in enumerate(data)
        ]
        table_block = {
            "type": "table",
            "tableId": table_id,
            "columnCount": len(headers),
            "rows": [header_row, *data_rows],
            "id": "b1",
            "part": "word/document.xml",
            "order": 1,
            "page": 1,
            "segmentIndex": 1,
        }
        return ParsedDocument(
            metadata={},
            package_info={},
            blocks=cast(Any, [table_block]),
            relationships=[],
            styles=[],
            warnings=[],
        )

    def test_table_row_slice(self) -> None:
        parsed = self._make_table(["Name", "Value"], [["A", "1"], ["B", "2"], ["C", "3"]])
        results = _render_resource(parsed, "table", "t1", rows="3-4")
        self.assertEqual(len(results), 1)
        html = results[0]
        self.assertIn("<tr>B|", html)
        self.assertIn("<tr>C|", html)

    def test_table_column_filter(self) -> None:
        parsed = self._make_table(["Name", "Age", "City"], [["Alice", "30", "NYC"], ["Bob", "25", "LA"]])
        results = _render_resource(parsed, "table", "t1", columns=["Name", "City"])
        self.assertEqual(len(results), 1)
        html = results[0]
        self.assertIn("Name|City", html)
        self.assertIn("Alice|NYC", html)

    def test_table_aggregate_sum(self) -> None:
        parsed = self._make_table(["Item", "Price"], [["A", "10"], ["B", "20"], ["C", "30"]])
        results = _render_resource(parsed, "table", "t1", aggregate="sum", aggregate_column="Price")
        self.assertEqual(len(results), 1)
        html = results[0]
        self.assertIn("<aggregate op=sum column=Price>60.0", html)

    def test_table_aggregate_avg(self) -> None:
        parsed = self._make_table(["Item", "Score"], [["X", "100"], ["Y", "200"]])
        results = _render_resource(parsed, "table", "t1", aggregate="avg", aggregate_column="Score")
        self.assertEqual(len(results), 1)
        html = results[0]
        self.assertIn("<aggregate op=avg column=Score>150.0", html)

    def test_table_aggregate_count(self) -> None:
        parsed = self._make_table(["Item", "Qty"], [["A", "5"], ["B", ""], ["C", "15"]])
        results = _render_resource(parsed, "table", "t1", aggregate="count", aggregate_column="Qty")
        self.assertEqual(len(results), 1)
        html = results[0]
        self.assertIn("<aggregate op=count column=Qty>2", html)

    def test_table_rows_and_columns_combined(self) -> None:
        parsed = self._make_table(["Name", "Score", "Rank"], [["A", "100", "1"], ["B", "200", "2"], ["C", "300", "3"]])
        results = _render_resource(parsed, "table", "t1", rows="2-3", columns=["Name", "Score"])
        self.assertEqual(len(results), 1)
        html = results[0]
        self.assertIn("A|100", html)
        self.assertIn("B|200", html)

    def test_table_aggregate_unknown_column_raises(self) -> None:
        parsed = self._make_table(["A", "B"], [["1", "2"]])
        with self.assertRaises(ValueError):
            _render_resource(parsed, "table", "t1", aggregate="sum", aggregate_column="NoSuch")

    def test_table_rows_invalid_range_raises(self) -> None:
        parsed = self._make_table(["X"], [["1"], ["2"]])
        with self.assertRaises(ValueError):
            _render_resource(parsed, "table", "t1", rows="5-3")


if __name__ == "__main__":
    unittest.main()
