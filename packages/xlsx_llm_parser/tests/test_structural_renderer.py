"""Direct coverage for XLSX structural renderer branches."""

from __future__ import annotations

import unittest
from typing import Any, cast

from xlsx_llm_parser.formats import FormatIndex
from xlsx_llm_parser.renderers.structural import render_range, render_workbook


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
                "conditional_formats": [{"ranges": "B2:B4", "ruleType": "cellIs", "formula": "B2>0"}],
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
        structural = render_workbook(wb, density="structural")
        semantic = render_workbook(wb, density="semantic")
        plain = render_workbook(wb, density="plain")

        for html in (structural, semantic):
            self.assertIn("<columns ref=B:C hidden>", html)
            self.assertIn("<sheetProtection/>", html)
            self.assertIn('<definedName name=VisibleName refersTo="Data!$A$1">', html)
            self.assertIn('<condition col=0 type=values values="Alice"/>', html)
            self.assertIn("<dataValidation ref=B2:B4 type=whole/>", html)
            self.assertIn('<rule type=cellIs formula="B2&gt;0"/>', html)
            self.assertIn("<externalLink target=other.xlsx/>", html)
            self.assertIn("<image id=image1 ref=D4/>", html)
            self.assertIn("names=Q1", html)
            self.assertIn("<pivotTable id=pivot1 name=Pivot/>", html)
            self.assertIn("<chartsheet name=ChartOnly>", html)
            self.assertIn("colspan=2", html)
            self.assertIn("rowspan=2", html)
            self.assertIn('formula="SUM(B3:B4)"', html)
            self.assertIn("formulaType=array", html)
            self.assertIn("formulaRange=B2:B4", html)
            self.assertIn("spillRange=B2:B4", html)

        self.assertIn('<a href="https://example.test/a">Alice</a>', structural)
        self.assertIn("<commentref id=comment0/>", structural)
        self.assertIn('<a href="https://example.test/a"><b>Ali</b>ce</a>', semantic)
        self.assertIn("<comment id=comment0", structural)
        self.assertIn("<comment id=comment0", semantic)

        self.assertIn("[Table Sales: Name, Amount]", plain)
        self.assertNotIn("<table id=table1", plain)

    def test_render_range_and_missing_sheet(self) -> None:
        wb = cast(Any, _workbook())
        html = render_range(wb, "Data", "A1:B2", density="structural")
        self.assertIn("<grid ref=A1:B2>", html)
        with self.assertRaises(ValueError):
            render_range(wb, "Missing", "A1:B2")

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

        html = render_workbook(cast(Any, workbook), density="semantic")

        self.assertIn('<styleRange ref=A1:C3 attrs="fill=#D9EAD3"/>', html)
        self.assertEqual(html.count("fill=#D9EAD3"), 1)


if __name__ == "__main__":
    unittest.main()
