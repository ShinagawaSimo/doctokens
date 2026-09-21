"""Direct coverage for XLSX structural renderer branches."""

from __future__ import annotations

import unittest
from typing import Any, cast
from xml.etree import ElementTree as ET

from xlsx_llm_parser.parsing.modules.styles.index import FormatIndex
from xlsx_llm_parser.rendering.dtx import iter_dtx, render_sheet_dtx
from xlsx_llm_parser.rendering.plain import iter_plain
from xlsx_llm_parser.rendering.selection import filter_rows, find_sheet, parse_range


def _workbook() -> dict[str, object]:
    return {
        "sheets": [
            {
                "name": "Data",
                "part": "xl/worksheets/sheet1.xml",
                "rows": [
                    [
                        {"ref": "A1", "row": 1, "col": 1, "text": "Name"},
                        {"ref": "B1", "row": 1, "col": 2, "text": "Amount"},
                    ],
                    [
                        {
                            "ref": "A2",
                            "row": 2,
                            "col": 1,
                            "text": "Alice",
                            "rich": [{"text": "Ali", "bold": True}, {"text": "ce"}],
                            "hyperlink": "https://example.test/a",
                            "comment": "Looks good",
                            "commentAuthor": "QA",
                        },
                        {
                            "ref": "B2",
                            "row": 2,
                            "col": 2,
                            "text": "10",
                            "formula": "SUM(B3:B4)",
                            "formulaType": "array",
                            "formulaRange": "B2:B4",
                            "spillRange": "B2:B4",
                            "colspan": 2,
                            "rowspan": 2,
                            "style": 0,
                        },
                    ],
                ],
                "hidden_cols": [(2, 3)],
                "sheet_protection": True,
                "filter_range": "A1:B2",
                "filter_cols": [{"col": 0, "type": "values", "values": ["Alice"]}],
                "data_validations": [{"ranges": "B2:B4", "type": "whole"}],
                "conditional_formats": [{"ranges": "B2:B4", "ruleType": "cellIs", "formulas": ["B2>0"]}],
                "images": [{"id": "image1", "ref": "D4"}],
                "charts": [
                    {
                        "id": "chart1",
                        "ref": "E5",
                        "type": "bar",
                        "title": "Sales",
                        "series_count": 1,
                        "series": [{"index": 1, "name": "Q1"}],
                    }
                ],
                "pivot_tables": [{"id": "pivot1", "ref": "", "name": "Pivot"}],
                "tables": [
                    {
                        "id": "table1",
                        "name": "Sales",
                        "ref": "A1:B2",
                        "columns": ["Name", "Amount"],
                        "totalsRow": True,
                    }
                ],
            },
            {"name": "ChartOnly", "kind": "chartsheet", "rows": []},
        ],
        "metadata": {
            "source": "memory",
            "defined_names": [
                {
                    "name": "VisibleName",
                    "ref": "Data!$A$1",
                    "scopeSheet": "Data",
                    "hidden": False,
                },
                {
                    "name": "_xlnm.Print_Area",
                    "ref": "Data!$A$1:$B$2",
                    "scopeSheet": "Data",
                    "hidden": False,
                },
                {"name": "OtherSheet", "ref": "Other!$A$1", "scopeSheet": "Other", "hidden": False},
            ],
            "external_links": ["other.xlsx"],
        },
        "fmt_index": FormatIndex(),
    }


class StructuralRendererTests(unittest.TestCase):
    def test_workbook_renders_metadata_and_inline_features(self) -> None:
        wb = cast(Any, _workbook())
        structural = ET.fromstring("".join(iter_dtx(wb, "structural")))
        semantic = ET.fromstring("".join(iter_dtx(wb, "semantic")))
        plain = "".join(iter_plain(wb))

        for root in (structural, semantic):
            self.assertEqual(root.find(".//columns").get("ref"), "B:C")
            self.assertEqual(root.find(".//columns").get("hidden"), "true")
            self.assertIsNotNone(root.find(".//sheet-protection"))
            self.assertEqual(root.find(".//defined-name").get("name"), "VisibleName")
            self.assertEqual(root.find(".//condition").get("values"), "Alice")
            self.assertEqual(root.find(".//data-validation").get("ref"), "B2:B4")
            self.assertEqual(root.find(".//conditional-format/rule").get("formula"), "B2>0")
            self.assertEqual(root.find(".//external-link").get("target"), "other.xlsx")
            self.assertEqual(root.find(".//img").get("id"), "image1")
            self.assertEqual(root.find(".//chart").get("names"), "Q1")
            self.assertEqual(root.find(".//pivot-table").get("id"), "pivot1")
            self.assertEqual(root.find("chart-sheet").get("name"), "ChartOnly")
            formula_cell = root.find(".//cell[@formula]")
            self.assertEqual(formula_cell.get("colspan"), "2")
            self.assertEqual(formula_cell.get("rowspan"), "2")
            self.assertEqual(formula_cell.get("formula"), "SUM(B3:B4)")
            self.assertEqual(formula_cell.get("formula-type"), "array")
            self.assertEqual(formula_cell.get("formula-range"), "B2:B4")
            self.assertEqual(formula_cell.get("spill-range"), "B2:B4")

        self.assertEqual(structural.find(".//cell/a").get("href"), "https://example.test/a")
        self.assertEqual(structural.find(".//comment-ref").get("id"), "comment0")
        self.assertEqual(semantic.find(".//cell/a/b").text, "Ali")
        self.assertIsNotNone(structural.find(".//comment[@id='comment0']"))
        self.assertIsNotNone(semantic.find(".//comment[@id='comment0']"))

        self.assertIn("[Table Sales: Name, Amount]", plain)
        self.assertNotIn("<table id=table1", plain)

        # Plain density keeps declaration info as text summaries, never output tags.
        self.assertIn("[Filter A1:B2]", plain)
        self.assertIn("[Image image1 at D4]", plain)
        self.assertIn("[Chart Sales: Q1]", plain)
        self.assertIn("[PivotTable Pivot]", plain)
        self.assertNotIn("<filter", plain)
        self.assertNotIn("<image", plain)
        self.assertNotIn("<chart ", plain)
        self.assertNotIn("<pivotTable", plain)

    def test_render_range_and_missing_sheet(self) -> None:
        wb = cast(Any, _workbook())
        sheet = find_sheet(wb, "Data")
        output = render_sheet_dtx(wb, sheet, "structural", filter_rows(sheet["rows"], *parse_range("A1:B2")))
        self.assertEqual(ET.fromstring(output).find(".//grid").get("ref"), "A1:B2")
        with self.assertRaises(ValueError):
            find_sheet(wb, "Missing")

    def test_empty_sheet_keeps_resource_declarations(self) -> None:
        workbook = {
            "sheets": [
                {
                    "name": "Empty",
                    "rows": [],
                    "images": [{"id": "image1", "ref": "A1"}],
                    "tables": [
                        {
                            "id": "table1",
                            "name": "T",
                            "ref": "A1:B2",
                            "columns": ["X", "Y"],
                            "totalsRow": False,
                        }
                    ],
                }
            ],
            "metadata": {"source": "memory"},
            "fmt_index": FormatIndex(),
        }
        root = ET.fromstring("".join(iter_dtx(cast(Any, workbook), "structural")))
        self.assertEqual(root.find(".//img").get("id"), "image1")
        self.assertEqual(root.find(".//table-summary").get("id"), "table1")
        self.assertIsNone(root.find(".//grid"))

    def test_semantic_repeated_styles_render_as_range(self) -> None:
        fmt_index = FormatIndex()
        fmt_index.register_font({})
        fmt_index.register_fill({"fill": "#D9EAD3"})
        fmt_index.register_cell_format(0, "", 0, 0)
        workbook = {
            "sheets": [
                {
                    "name": "Data",
                    "rows": [
                        [
                            {"ref": f"{col}{row}", "row": row, "col": col_idx, "text": f"{col}{row}", "style": 0}
                            for col_idx, col in enumerate(("A", "B", "C"), start=1)
                        ]
                        for row in range(1, 4)
                    ],
                }
            ],
            "metadata": {"source": "memory"},
            "fmt_index": fmt_index,
        }

        output = "".join(iter_dtx(cast(Any, workbook), "semantic"))

        self.assertIn('<style-range fill="#D9EAD3" ref="A1:C3" />', output)
        self.assertEqual(output.count("#D9EAD3"), 1)


if __name__ == "__main__":
    unittest.main()
