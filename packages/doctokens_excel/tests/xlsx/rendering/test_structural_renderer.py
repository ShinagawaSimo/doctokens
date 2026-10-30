"""Direct coverage for XLSX structural renderer branches."""

from __future__ import annotations

import unittest
from typing import Any, cast

from doctokens_excel.xlsx.parsing.modules.styles.index import FormatIndex
from doctokens_excel.xlsx.rendering.dtx import iter_dtx
from doctokens_excel.xlsx.rendering.selection import find_sheet


class StructuralRendererTests(unittest.TestCase):
    def test_missing_sheet_is_explicit(self) -> None:
        with self.assertRaises(ValueError):
            find_sheet({"sheets": []}, "Missing")

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
