"""测试 inline 解析和轻量 XML 渲染。"""

from __future__ import annotations

import unittest
from io import BytesIO
from typing import Any, cast
from xml.etree import ElementTree as ET

from docx_llm_parser.core.models import ParseOptions, ParseWarning, RelationshipRecord
from docx_llm_parser.core.package import PackageReader
from docx_llm_parser.core.relationships import RelationshipIndex
from docx_llm_parser.extractors.body import DocumentBodyParser
from docx_llm_parser.extractors.inline import InlineParser
from docx_llm_parser.extractors.objects import (
    CHART_REL_TYPE,
    DIAGRAM_DATA_REL_TYPE,
    EmbeddedObjectExtractor,
    parse_chart_root,
    parse_smartart_root,
)
from docx_llm_parser.ooxml.numbering import NumberingMap, NumberingState
from docx_llm_parser.ooxml.styles import StyleMap
from docx_llm_parser.renderers.inline.content import inline_content as _inline_content
from docx_llm_parser.renderers.tables.render import nested_table as _nested_table

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
        return _inline_content(cast(Any, {"text": "", "runs": runs}), "L2")

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
        return _inline_content(cast(Any, {"text": "", "runs": runs}), "L2")

    def test_omml_equation_renders_as_eq(self) -> None:
        """OMML 公式应进入最终 XML，而不是只进入 debug。"""
        xml = f"<w:p {NS}><m:oMath><m:r><m:t>x+1=y</m:t></m:r></m:oMath></w:p>"

        self.assertEqual(self._render_paragraph(xml), "<equation>x+1=y</equation>")

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
            "<textbox alt=desc>text box</textbox>",
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
            "<textbox alt=old box>vml text</textbox>",
        )

    def test_note_self_reference_is_not_warning_noise(self) -> None:
        """尾注正文内的自编号标记不应进入最终 XML 或 warning。"""
        xml = f"<w:p {NS}><w:r><w:endnoteRef /></w:r><w:r><w:t>note text</w:t></w:r></w:p>"

        self.assertEqual(self._render_paragraph(xml), "note text")
        self.assertEqual(self.warnings, [])

    def test_nested_table_renders_structured_xml(self) -> None:
        """单元格内嵌套表格不能再压缩成纯文本。"""
        nested = {
            "type": "table",
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

        self.assertEqual(
            _nested_table(cast(Any, nested)),
            "<nestedtable rows=1 cols=3><row><td>A<td colspan=2>B",
        )

    def test_vertical_merge_updates_origin_rowspan(self) -> None:
        """vMerge continue 应推动 restart 起点的 rowSpan。"""
        rows = [
            {
                "rowIndex": 0,
                "cells": [
                    {
                        "rowIndex": 0,
                        "colIndex": 0,
                        "rowSpan": 1,
                        "colSpan": 1,
                        "text": "A",
                        "blocks": [],
                        "vMerge": "restart",
                    }
                ],
            },
            {
                "rowIndex": 1,
                "cells": [
                    {
                        "rowIndex": 1,
                        "colIndex": 0,
                        "rowSpan": 1,
                        "colSpan": 1,
                        "text": "",
                        "blocks": [],
                        "vMerge": "continue",
                    }
                ],
            },
        ]
        numbering = NumberingMap({}, {}, self.warnings)
        parser = DocumentBodyParser(
            cast(PackageReader, object()),
            StyleMap({}, self.warnings),
            ParseOptions(),
            self.warnings,
            RelationshipIndex.from_records([]),
            {},
            {},
            NumberingState(numbering, self.warnings),
        )

        parser._apply_vertical_merges(cast(Any, rows))

        self.assertEqual(rows[0]["cells"][0]["rowSpan"], 2)  # type: ignore[index]

    def test_chart_cache_renders_as_chart_summary(self) -> None:
        """图表缓存数据应渲染为轻量 chart 摘要。"""
        chart_xml = f"""<c:chartSpace {NS}>
          <c:chart>
            <c:title><c:tx><c:rich><a:p><a:r><a:t>人口趋势</a:t></a:r></a:p></c:rich></c:tx></c:title>
            <c:plotArea><c:barChart><c:ser>
              <c:tx><c:strRef><c:strCache><c:pt idx="0"><c:v>人群A</c:v></c:pt>
              </c:strCache></c:strRef></c:tx>
              <c:cat><c:strRef><c:strCache>
                <c:pt idx="0"><c:v>一期</c:v></c:pt><c:pt idx="1"><c:v>二期</c:v></c:pt>
              </c:strCache></c:strRef></c:cat>
              <c:val><c:numRef><c:numCache>
                <c:pt idx="0"><c:v>1.5</c:v></c:pt><c:pt idx="1"><c:v>2.5</c:v></c:pt>
              </c:numCache></c:numRef></c:val>
            </c:ser></c:barChart></c:plotArea>
          </c:chart>
        </c:chartSpace>"""
        chart = parse_chart_root(ET.fromstring(chart_xml), "chart1", "word/charts/chart1.xml")
        xml = f"""<w:p {NS}><w:r><w:drawing><wp:inline>
          <a:graphic><a:graphicData><c:chart r:id="rIdChart"/></a:graphicData></a:graphic>
        </wp:inline></w:drawing></w:r></w:p>"""

        rendered = self._render_with_objects(xml, {("word/document.xml", "rIdChart"): chart})

        self.assertIn("<chart id=chart1 type=bar title=人口趋势 series=1", rendered)
        self.assertIn("truncated", rendered)
        self.assertIn("names=人群A", rendered)
        self.assertIn("categories=一期,二期", rendered)

    def test_smartart_data_renders_nodes_and_links(self) -> None:
        """SmartArt data model 应输出节点文本和连接关系。"""
        smartart_xml = f"""<dgm:dataModel {NS}>
          <dgm:ptLst>
            <dgm:pt modelId="n1"><dgm:t><a:p><a:r><a:t>采集</a:t></a:r></a:p></dgm:t></dgm:pt>
            <dgm:pt modelId="n2"><dgm:t><a:p><a:r><a:t>分析</a:t></a:r></a:p></dgm:t></dgm:pt>
          </dgm:ptLst>
          <dgm:cxnLst><dgm:cxn modelId="c1" type="parOf" srcId="n1" destId="n2"/></dgm:cxnLst>
        </dgm:dataModel>"""
        smartart = parse_smartart_root(ET.fromstring(smartart_xml), "smartart1", "word/diagrams/data1.xml")
        xml = f"""<w:p {NS}><w:r><w:drawing><wp:inline>
          <a:graphic><a:graphicData><dgm:relIds r:dm="rIdDm"/></a:graphicData></a:graphic>
        </wp:inline></w:drawing></w:r></w:p>"""

        rendered = self._render_with_objects(xml, {("word/document.xml", "rIdDm"): smartart})

        self.assertIn("<smartart id=smartart1 type= nodes=2 links=1 truncated>采集 分析", rendered)

    def test_embedded_object_extractor_builds_lookup(self) -> None:
        """对象解析器应按 relationship 建立 chart/SmartArt 查询索引。"""
        chart_xml = f"""<c:chartSpace {NS}><c:chart>
          <c:plotArea><c:lineChart><c:ser>
            <c:val><c:numRef><c:numCache><c:pt idx="0"><c:v>3</c:v></c:pt>
            </c:numCache></c:numRef></c:val>
          </c:ser></c:lineChart></c:plotArea>
        </c:chart></c:chartSpace>"""
        smartart_xml = f"""<dgm:dataModel {NS}><dgm:ptLst>
          <dgm:pt modelId="n1"><dgm:t><a:p><a:r><a:t>节点</a:t></a:r></a:p></dgm:t></dgm:pt>
        </dgm:ptLst></dgm:dataModel>"""
        package = FakePackage(
            {
                "word/charts/chart1.xml": chart_xml,
                "word/diagrams/data1.xml": smartart_xml,
            }
        )
        relationships = RelationshipIndex.from_records(
            [
                RelationshipRecord(
                    source_part="word/document.xml",
                    id="rChart",
                    type=CHART_REL_TYPE,
                    target="charts/chart1.xml",
                    resolved_target="word/charts/chart1.xml",
                ),
                RelationshipRecord(
                    source_part="word/document.xml",
                    id="rDm",
                    type=DIAGRAM_DATA_REL_TYPE,
                    target="diagrams/data1.xml",
                    resolved_target="word/diagrams/data1.xml",
                ),
            ]
        )

        lookup, charts, smartarts = EmbeddedObjectExtractor(cast(Any, package), relationships, self.warnings).extract()

        self.assertEqual(charts[0]["chartType"], "line")
        self.assertEqual(smartarts[0]["nodes"][0]["text"], "节点")
        self.assertEqual(lookup[("word/document.xml", "rChart")]["id"], "chart1")
        self.assertEqual(lookup[("word/document.xml", "rDm")]["id"], "smartart1")


class FakePackage:
    """测试用最小 package reader。"""

    def __init__(self, parts: dict[str, str]) -> None:
        self.parts = parts

    def exists(self, name: str) -> bool:
        # 对象解析器只需要 exists/open_entry 两个接口。
        return name in self.parts

    def open_entry(self, name: str) -> BytesIO:
        return BytesIO(self.parts[name].encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
