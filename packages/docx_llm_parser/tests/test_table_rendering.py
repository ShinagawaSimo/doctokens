"""Regression tests for stable table identity and truncation."""

from __future__ import annotations

import unittest
from typing import Any, cast
from xml.etree import ElementTree as ET

from docx_llm_parser.core.models import ParsedDocument
from docx_llm_parser.rendering.dispatch import render_resource as _render_resource
from docx_llm_parser.rendering.plain.helpers import table_text_only


class TableIdentityTests(unittest.TestCase):
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

        table_outputs = _render_resource(parsed, "tables")
        self.assertEqual(len(table_outputs), 1)
        table = ET.fromstring(table_outputs[0]).find(".//table")
        assert table is not None
        self.assertEqual(table.attrib["id"], "t1")
        self.assertEqual(table.attrib["rows"], "2")
        self.assertEqual(table.attrib["cols"], "3")

        results = _render_resource(parsed, "table", "t1")
        self.assertEqual(len(results), 1)
        table = ET.fromstring(results[0]).find(".//table")
        assert table is not None
        self.assertEqual(table.attrib["id"], "t1")
        self.assertEqual(table.attrib["rows"], "2")
        self.assertEqual(table.attrib["cols"], "3")

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
        output = results[0]
        table = ET.fromstring(output).find(".//table")
        assert table is not None
        self.assertEqual([[cell.text for cell in row.findall("td")] for row in table.findall("tr")], [["B", "2"], ["C", "3"]])

    def test_table_column_filter(self) -> None:
        parsed = self._make_table(["Name", "Age", "City"], [["Alice", "30", "NYC"], ["Bob", "25", "LA"]])
        results = _render_resource(parsed, "table", "t1", columns=["Name", "City"])
        self.assertEqual(len(results), 1)
        output = results[0]
        table = ET.fromstring(output).find(".//table")
        assert table is not None
        self.assertEqual(
            [[cell.text for cell in row.findall("td")] for row in table.findall("tr")],
            [["Name", "City"], ["Alice", "NYC"], ["Bob", "LA"]],
        )

    def test_table_aggregate_sum(self) -> None:
        parsed = self._make_table(["Item", "Price"], [["A", "10"], ["B", "20"], ["C", "30"]])
        results = _render_resource(parsed, "table", "t1", aggregate="sum", aggregate_column="Price")
        self.assertEqual(len(results), 1)
        output = results[0]
        aggregate = ET.fromstring(output).find(".//aggregate")
        assert aggregate is not None
        self.assertEqual(aggregate.attrib, {"column": "Price", "op": "sum"})
        self.assertEqual(aggregate.text, "60.0")

    def test_table_aggregate_avg(self) -> None:
        parsed = self._make_table(["Item", "Score"], [["X", "100"], ["Y", "200"]])
        results = _render_resource(parsed, "table", "t1", aggregate="avg", aggregate_column="Score")
        self.assertEqual(len(results), 1)
        output = results[0]
        aggregate = ET.fromstring(output).find(".//aggregate")
        assert aggregate is not None
        self.assertEqual(aggregate.attrib, {"column": "Score", "op": "avg"})
        self.assertEqual(aggregate.text, "150.0")

    def test_table_aggregate_count(self) -> None:
        parsed = self._make_table(["Item", "Qty"], [["A", "5"], ["B", ""], ["C", "15"]])
        results = _render_resource(parsed, "table", "t1", aggregate="count", aggregate_column="Qty")
        self.assertEqual(len(results), 1)
        output = results[0]
        aggregate = ET.fromstring(output).find(".//aggregate")
        assert aggregate is not None
        self.assertEqual(aggregate.attrib, {"column": "Qty", "op": "count"})
        self.assertEqual(aggregate.text, "2")

    def test_table_rows_and_columns_combined(self) -> None:
        parsed = self._make_table(["Name", "Score", "Rank"], [["A", "100", "1"], ["B", "200", "2"], ["C", "300", "3"]])
        results = _render_resource(parsed, "table", "t1", rows="2-3", columns=["Name", "Score"])
        self.assertEqual(len(results), 1)
        output = results[0]
        table = ET.fromstring(output).find(".//table")
        assert table is not None
        self.assertEqual([[cell.text for cell in row.findall("td")] for row in table.findall("tr")], [["A", "100"], ["B", "200"]])

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
