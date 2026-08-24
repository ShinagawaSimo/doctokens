"""Direct tests for the XLSX query engine."""

from __future__ import annotations

import unittest
from typing import Any, cast

from xlsx_llm_parser.query import (
    _average_accumulator,
    _coerce_cell_value,
    _finalize_averages,
    _matches_condition,
    _order_key,
    _render_query_result,
    query_data,
)


def _workbook() -> dict[str, object]:
    return {
        "sheets": [
            {
                "name": "Data",
                "part": "xl/worksheets/sheet1.xml",
                "rows": [
                    [
                        {"ref": "A1", "row": 1, "col": 1, "text": "Region"},
                        {"ref": "B1", "row": 1, "col": 2, "text": "Rep"},
                        {"ref": "C1", "row": 1, "col": 3, "text": "Amount"},
                    ],
                    [
                        {"ref": "A2", "row": 2, "col": 1, "text": "East"},
                        {"ref": "B2", "row": 2, "col": 2, "text": "Alice"},
                        {"ref": "C2", "row": 2, "col": 3, "text": "10"},
                    ],
                    [
                        {"ref": "A3", "row": 3, "col": 1, "text": "West"},
                        {"ref": "B3", "row": 3, "col": 2, "text": "Bob"},
                        {"ref": "C3", "row": 3, "col": 3, "text": "20"},
                    ],
                    [
                        {"ref": "A4", "row": 4, "col": 1, "text": "East"},
                        {"ref": "B4", "row": 4, "col": 2, "text": "Cara"},
                        {"ref": "C4", "row": 4, "col": 3, "text": "30"},
                    ],
                ],
                "tables": [
                    {
                        "id": "sales",
                        "name": "Sales",
                        "ref": "A1:C4",
                        "columns": ["Region", "Rep", "Amount"],
                    }
                ],
            }
        ],
        "metadata": {"source": "memory"},
        "fmt_index": object(),
    }


class QueryEngineTests(unittest.TestCase):
    def test_range_query_uses_header_select_order_and_limit(self) -> None:
        result = query_data(
            cast(Any, _workbook()),
            sheet="Data",
            range_spec="A1:C4",
            header_row=1,
            where=[{"column": "Region", "op": "eq", "value": "East"}],
            select=["Rep", "Amount"],
            order_by=[{"column": "Rep", "direction": "desc"}],
            limit=1,
        )

        self.assertIn("<th>Rep", result)
        self.assertIn("<td>Cara", result)
        self.assertIn("<td>30", result)
        self.assertNotIn("Alice", result)

    def test_range_query_preserves_blank_header_columns(self) -> None:
        workbook = {
            "sheets": [
                {
                    "name": "Data",
                    "rows": [
                        [
                            {"ref": "B1", "row": 1, "col": 2, "text": "Young"},
                            {"ref": "C1", "row": 1, "col": 3, "text": "Adult"},
                        ],
                        [
                            {"ref": "A2", "row": 2, "col": 1, "text": "Site A"},
                            {"ref": "B2", "row": 2, "col": 2, "text": "10%"},
                            {"ref": "C2", "row": 2, "col": 3, "text": "90%"},
                        ],
                    ],
                    "tables": [],
                }
            ],
            "metadata": {"source": "memory"},
            "fmt_index": object(),
        }

        wb = cast(Any, workbook)
        result = query_data(wb, sheet="Data", range_spec="A1:C2", header_row=1)

        self.assertIn("<th><th>Young<th>Adult", result)
        self.assertNotIn("Col1", result)
        self.assertIn("<td>Site A<td>10%<td>90%", result)

        selected = query_data(wb, sheet="Data", range_spec="A1:C2", header_row=1, select=["A", "Adult"])
        self.assertIn("<th><th>Adult", selected)
        self.assertIn("<td>Site A<td>90%", selected)

    def test_table_query_filters_contains_gt_and_lt(self) -> None:
        result = query_data(
            cast(Any, _workbook()),
            table_id="sales",
            where=[
                {"column": "Rep", "op": "contains", "value": "a"},
                {"column": "Amount", "op": "gt", "value": 15},
                {"column": "Amount", "op": "lt", "value": 35},
            ],
        )

        self.assertIn("Cara", result)
        self.assertNotIn("Alice", result)
        self.assertNotIn("Bob", result)

    def test_grouped_aggregates_render_aliases(self) -> None:
        result = query_data(
            cast(Any, _workbook()),
            table_id="sales",
            group_by=["Region"],
            aggregates=[
                {"op": "sum", "column": "Amount", "as": "total"},
                {"op": "avg", "column": "Amount", "as": "mean"},
                {"op": "min", "column": "Amount", "as": "low"},
                {"op": "max", "column": "Amount", "as": "high"},
                {"op": "count", "column": "Rep", "as": "count"},
            ],
            order_by=[{"column": "Region"}],
        )

        self.assertIn("<th>total", result)
        self.assertIn("<td>40", result)
        self.assertIn("<td>20.0", result)
        self.assertIn("<td>2", result)

    def test_invalid_sources_raise(self) -> None:
        wb = cast(Any, _workbook())
        with self.assertRaises(ValueError):
            query_data(wb, table_id="missing")
        with self.assertRaises(ValueError):
            query_data(wb)

    def test_unsupported_where_operator_raises(self) -> None:
        with self.assertRaises(ValueError):
            query_data(
                cast(Any, _workbook()),
                table_id="sales",
                where=[{"column": "Rep", "op": "unsupported", "value": "Alice"}],
            )

    def test_unknown_column_raises(self) -> None:
        with self.assertRaises(ValueError):
            query_data(
                cast(Any, _workbook()),
                table_id="sales",
                where=[{"column": "Nope", "op": "eq", "value": "Alice"}],
            )

    def test_numeric_order_by_sorts_by_value(self) -> None:
        workbook = {
            "sheets": [
                {
                    "name": "Data",
                    "rows": [
                        [{"ref": "A1", "row": 1, "col": 1, "text": "Amount"}],
                        [{"ref": "A2", "row": 2, "col": 1, "text": "100"}],
                        [{"ref": "A3", "row": 3, "col": 1, "text": "9"}],
                        [{"ref": "A4", "row": 4, "col": 1, "text": "10"}],
                    ],
                    "tables": [],
                }
            ],
            "metadata": {"source": "memory"},
            "fmt_index": object(),
        }
        result = query_data(
            cast(Any, workbook),
            sheet="Data",
            range_spec="A1:A4",
            header_row=1,
            order_by=[{"column": "Amount"}],
        )
        self.assertIn("<td>9<tr><td>10<tr><td>100", result)

    def test_query_value_helpers_cover_empty_and_invalid_paths(self) -> None:
        self.assertEqual(_coerce_cell_value("1.5"), 1.5)
        self.assertEqual(_coerce_cell_value("text"), "text")
        row = {"name": "Alice", "amount": 10}
        self.assertTrue(_matches_condition(row, {"column": "name", "op": "eq", "value": "Alice"}))
        self.assertTrue(_matches_condition(row, {"column": "name", "op": "contains", "value": "li"}))
        self.assertTrue(_matches_condition(row, {"column": "amount", "op": "gt", "value": "9"}))
        self.assertTrue(_matches_condition(row, {"column": "amount", "op": "lt", "value": "11"}))
        self.assertFalse(_matches_condition(row, {"column": "amount", "op": "gt", "value": "bad"}))
        self.assertFalse(_matches_condition(row, {"column": "name", "op": "unknown", "value": "Alice"}))
        self.assertEqual(_average_accumulator((1, 1), 2), (3, 2))
        self.assertEqual(_average_accumulator(("bad", 1), 2), (2, 1))
        average_row: dict[str, object] = {"avg_amount": (3, 2)}
        _finalize_averages(average_row, [{"op": "avg", "column": "amount", "as": "avg_amount"}])
        self.assertEqual(average_row["avg_amount"], 1.5)
        empty_average: dict[str, object] = {}
        _finalize_averages(empty_average, [{"op": "avg", "column": "amount"}])
        self.assertEqual(empty_average["avg_amount"], 0)
        self.assertEqual(_order_key({"value": 2}, "value"), (0, 2))
        self.assertEqual(_order_key({"value": "2"}, "value"), (1, "2"))
        self.assertEqual(_render_query_result([]), "<table>\n")


if __name__ == "__main__":
    unittest.main()
