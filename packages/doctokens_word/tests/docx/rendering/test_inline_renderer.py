"""测试 inline 解析和轻量 XML 渲染。"""

from __future__ import annotations

import unittest
from typing import Any, cast
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.relationships import RelationshipIndex
from doctokens_word.docx.model import ParseOptions, ParseWarning
from doctokens_word.docx.ooxml.styles import StyleMap
from doctokens_word.docx.parsing.modules.body.inline import InlineParser
from doctokens_word.docx.rendering.dtx import _append_inline, _append_table

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
    'xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
)


class InlineRendererTests(unittest.TestCase):
    """覆盖 LLM XML 最关心的新增 inline 对象。"""

    def setUp(self) -> None:
        # 每个测试创建独立 parser，避免共享 warnings 或解析状态。
        self.warnings: list[ParseWarning] = []
        self.parser = InlineParser(
            StyleMap({}, self.warnings),
            ParseOptions(),
            self.warnings,
            RelationshipIndex.from_records([]),
            {},
        )

    def _render_paragraph(self, xml: str) -> str:
        """解析一段 OOXML 并渲染为段落内 XML。"""
        p = ET.fromstring(xml)
        runs, _hints = self.parser.paragraph_runs(p, "word/document.xml", "b-test", None)
        output = ET.Element("p")
        _append_inline(output, cast(Any, {"text": "", "runs": runs}), "semantic", {})
        return ET.tostring(output, encoding="unicode")

    def _render_with_objects(self, xml: str, object_lookup: dict[tuple[str, str], object] | None = None) -> str:
        """使用预解析对象索引渲染一段 OOXML。"""
        parser = InlineParser(
            StyleMap({}, self.warnings),
            ParseOptions(),
            self.warnings,
            RelationshipIndex.from_records([]),
            {},
            object_lookup=cast(Any, object_lookup) if object_lookup else None,
        )
        p = ET.fromstring(xml)
        runs, _hints = parser.paragraph_runs(p, "word/document.xml", "b-test", None)
        output = ET.Element("p")
        _append_inline(output, cast(Any, {"text": "", "runs": runs}), "semantic", {})
        return ET.tostring(output, encoding="unicode")

    def test_omml_equation_renders_as_eq(self) -> None:
        """OMML 公式应进入最终 XML。"""
        xml = f"<w:p {NS}><m:oMath><m:r><m:t>x+1=y</m:t></m:r></m:oMath></w:p>"

        self.assertEqual(self._render_paragraph(xml), '<p><equation notation="latex">x+1=y</equation></p>')

    def test_drawingml_textbox_renders_as_textbox(self) -> None:
        """DrawingML/WPS 文本框应保留文字和有语义的 alt。"""
        xml = f"""<w:p {NS}>
          <w:r><w:drawing><wp:inline>
            <wp:docPr id="1" name="Box 1" descr="desc"/>
            <wps:txbx><w:txbxContent><w:p><w:r><w:t>text box</w:t></w:r></w:p>
            </w:txbxContent></wps:txbx>
          </wp:inline></w:drawing></w:r>
        </w:p>"""

        self.assertEqual(
            self._render_paragraph(xml),
            '<p><textbox alt="desc">text box</textbox></p>',
        )

    def test_vml_textbox_renders_as_textbox(self) -> None:
        """旧式 VML 文本框也应保留文字。"""
        xml = f"""<w:p {NS}>
          <w:r><w:pict><v:shape id="shape1" alt="old box">
            <w:txbxContent><w:p><w:r><w:t>vml text</w:t></w:r></w:p></w:txbxContent>
          </v:shape></w:pict></w:r>
        </w:p>"""

        self.assertEqual(
            self._render_paragraph(xml),
            '<p><textbox alt="old box">vml text</textbox></p>',
        )

    def test_note_self_reference_is_not_warning_noise(self) -> None:
        """尾注正文内的自编号标记不应进入最终 XML 或 warning。"""
        xml = f"<w:p {NS}><w:r><w:endnoteRef /></w:r><w:r><w:t>note text</w:t></w:r></w:p>"

        self.assertEqual(self._render_paragraph(xml), "<p>note text</p>")
        self.assertEqual(self.warnings, [])

    def test_nested_table_renders_structured_xml(self) -> None:
        """单元格内嵌套表格不能再压缩成纯文本。"""
        nested = {
            "type": "table",
            "tableId": "inner",
            "rows": [
                {
                    "rowIndex": 0,
                    "cells": [
                        {
                            "rowIndex": 0,
                            "colIndex": 0,
                            "rowSpan": 1,
                            "colSpan": 1,
                            "text": "A",
                            "blocks": [{"type": "paragraph", "text": "A", "runs": [{"text": "A"}]}],
                        },
                        {
                            "rowIndex": 0,
                            "colIndex": 1,
                            "rowSpan": 1,
                            "colSpan": 2,
                            "text": "B",
                            "blocks": [{"type": "paragraph", "text": "B", "runs": [{"text": "B"}]}],
                        },
                    ],
                }
            ],
            "columnCount": 3,
        }

        output = ET.Element("root")
        _append_table(output, cast(Any, nested), "semantic", {})
        self.assertEqual(
            ET.tostring(output, encoding="unicode"),
            '<root><table id="inner"><tr><td><p>A</p></td><td colspan="2"><p>B</p></td></tr></table></root>',
        )


if __name__ == "__main__":
    unittest.main()
