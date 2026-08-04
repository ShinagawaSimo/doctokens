"""Shared test fixtures for building synthetic DOCX packages."""

import base64
import zipfile
from pathlib import Path

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
    'xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)


def write_rich_docx(path: Path) -> None:
    """Write a synthetic DOCX with headings, tables, charts, smartarts, images, notes."""
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": _content_types_xml(),
        "_rels/.rels": _rels_xml([]),
        "word/document.xml": _document_xml(),
        "word/_rels/document.xml.rels": _document_relationships_xml(),
        "word/styles.xml": _styles_xml(),
        "word/numbering.xml": _numbering_xml(),
        "word/footnotes.xml": _notes_xml("footnotes", "footnote", "Footnote text"),
        "word/endnotes.xml": _notes_xml("endnotes", "endnote", "Endnote text"),
        "word/comments.xml": _comments_xml(),
        "word/header1.xml": _simple_part_xml("Header text"),
        "word/footer1.xml": _simple_part_xml("Footer text"),
        "word/media/image1.png": PNG_BYTES,
        "word/charts/chart1.xml": _chart_xml(),
        "word/diagrams/data1.xml": _smartart_xml(),
        "word/diagrams/layout1.xml": _layout_xml(),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>"""


def _rels_xml(rows: list[str]) -> str:
    return (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rows)
        + "</Relationships>"
    )


def _document_relationships_xml() -> str:
    rows = [
        _relationship("rLink", "hyperlink", "https://example.test", target_mode="External"),
        _relationship("rImg", "image", "media/image1.png"),
        _relationship("rChart", "chart", "charts/chart1.xml"),
        _relationship("rDm", "diagramData", "diagrams/data1.xml"),
        _relationship("rLayout", "diagramLayout", "diagrams/layout1.xml"),
    ]
    return _rels_xml(rows)


def _relationship(
    rel_id: str,
    rel_type: str,
    target: str,
    *,
    target_mode: str | None = None,
) -> str:
    mode = f' TargetMode="{target_mode}"' if target_mode else ""
    return (
        f'<Relationship Id="{rel_id}" '
        f'Type="{_rel_type_url(rel_type)}" '
        f'Target="{target}"{mode}/>'
    )


def _rel_type_url(rel_type: str) -> str:
    return f"http://schemas.openxmlformats.org/officeDocument/2006/relationships/{rel_type}"


def _document_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document {NS}><w:body>
  <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Document Title</w:t></w:r></w:p>
  <w:p><w:pPr><w:pStyle w:val="ListPara"/></w:pPr>
    <w:r><w:rPr><w:rStyle w:val="Emphasis"/><w:color w:val="00AA00"/>
      <w:shd w:fill="FFFF00"/></w:rPr><w:t>Hello</w:t></w:r>
    <w:hyperlink r:id="rLink"><w:r><w:t>link</w:t></w:r></w:hyperlink>
    <w:r><w:tab/><w:br w:type="page"/><w:t>after break</w:t></w:r>
    <w:r><w:footnoteReference w:id="2"/><w:endnoteReference w:id="3"/>
      <w:commentReference w:id="4"/></w:r>
    <w:r><w:instrText>PAGE</w:instrText></w:r>
    <w:ins><w:r><w:t> inserted</w:t></w:r></w:ins>
    <w:del><w:r><w:delText> deleted</w:delText></w:r></w:del>
    <m:oMath><m:r><m:t>x</m:t></m:r></m:oMath>
    <w:bookmarkStart w:id="9" w:name="bm"/><w:commentRangeStart w:id="4"/>
  </w:p>
  <w:p><w:r><w:drawing><wp:inline><wp:extent cx="1" cy="2"/>
    <wp:docPr id="1" name="Picture" descr="alt text"/>
    <a:graphic><a:graphicData><a:blip r:embed="rImg"/></a:graphicData></a:graphic>
  </wp:inline></w:drawing></w:r></w:p>
  <w:p><w:r><w:drawing><wp:inline><wp:docPr id="2" name="Chart"/>
    <a:graphic><a:graphicData><c:chart r:id="rChart"/></a:graphicData></a:graphic>
  </wp:inline></w:drawing></w:r></w:p>
  <w:p><w:r><w:drawing><wp:inline><wp:docPr id="3" name="SmartArt"/>
    <a:graphic><a:graphicData><dgm:relIds r:dm="rDm"/></a:graphicData></a:graphic>
  </wp:inline></w:drawing></w:r></w:p>
  <w:p><w:r><w:drawing><wp:inline><wp:docPr id="4" name="Textbox" descr="box alt"/>
    <wps:txbx><w:txbxContent><w:p><w:r><w:t>Box text</w:t></w:r></w:p>
    </w:txbxContent></wps:txbx>
  </wp:inline></w:drawing></w:r></w:p>
  <w:tbl>
    <w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr>
      <w:gridSpan w:val="2"/><w:vMerge w:val="restart"/></w:tcPr>
      <w:p><w:r><w:t>Head</w:t></w:r></w:p></w:tc></w:tr>
    <w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p><w:r><w:t>Body</w:t></w:r></w:p></w:tc></w:tr>
  </w:tbl>
  <w:p><w:r><w:lastRenderedPageBreak/><w:t>Last page</w:t></w:r></w:p>
  <w:sectPr/>
</w:body></w:document>"""


def _styles_xml() -> str:
    return f"""<w:styles {NS}>
  <w:style w:type="paragraph" w:styleId="Base">
    <w:name w:val="base"/><w:rPr><w:b/><w:color w:val="FF0000"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:basedOn w:val="Base"/>
    <w:pPr><w:outlineLvl w:val="0"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListPara">
    <w:name w:val="list"/><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/>
    </w:numPr></w:pPr>
  </w:style>
  <w:style w:type="character" w:styleId="Emphasis">
    <w:name w:val="emphasis"/><w:rPr><w:i/><w:u w:val="single"/>
      <w:highlight w:val="yellow"/><w:vertAlign w:val="superscript"/>
    </w:rPr>
  </w:style>
</w:styles>"""


def _numbering_xml() -> str:
    return f"""<w:numbering {NS}>
  <w:abstractNum w:abstractNumId="1">
    <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/><w:suff w:val="space"/><w:pStyle w:val="ListPara"/>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""


def _notes_xml(root_name: str, item_name: str, text: str) -> str:
    return f"""<w:{root_name} {NS}>
  <w:{item_name} w:id="1" w:type="separator"><w:p><w:r><w:t>sep</w:t></w:r></w:p></w:{item_name}>
  <w:{item_name} w:id="2"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:{item_name}>
  <w:{item_name} w:id="3"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:{item_name}>
</w:{root_name}>"""


def _comments_xml() -> str:
    return f"""<w:comments {NS}>
  <w:comment w:id="4" w:author="Reviewer" w:date="2026-08-01T00:00:00Z">
    <w:p><w:r><w:t>Comment text</w:t></w:r></w:p>
  </w:comment>
</w:comments>"""


def _simple_part_xml(text: str) -> str:
    return f"""<w:hdr {NS}><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:hdr>"""


def _chart_xml() -> str:
    return f"""<c:chartSpace {NS}><c:chart>
  <c:title><c:tx><c:rich><a:p><a:r><a:t>Chart Title</a:t></a:r></a:p>
  </c:rich></c:tx></c:title>
  <c:plotArea><c:barChart><c:ser>
    <c:tx><c:strRef><c:strCache><c:pt idx="0"><c:v>Series A</c:v></c:pt>
    </c:strCache></c:strRef></c:tx>
    <c:cat><c:strRef><c:strCache>
      <c:pt idx="0"><c:v>Q1</c:v></c:pt><c:pt idx="1"><c:v>Q2</c:v></c:pt>
    </c:strCache></c:strRef></c:cat>
    <c:val><c:numRef><c:f>Sheet1!A1:A2</c:f><c:numCache>
      <c:pt idx="0"><c:v>2</c:v></c:pt><c:pt idx="1"><c:v>5</c:v></c:pt>
    </c:numCache></c:numRef></c:val>
  </c:ser></c:barChart></c:plotArea>
</c:chart></c:chartSpace>"""


def _smartart_xml() -> str:
    return f"""<dgm:dataModel {NS}>
  <dgm:ptLst>
    <dgm:pt modelId="n1" type="node"><dgm:t><a:p><a:r><a:t>Start</a:t></a:r></a:p>
    </dgm:t></dgm:pt>
    <dgm:pt modelId="n2"><dgm:t><a:p><a:r><a:t>Finish</a:t></a:r></a:p>
    </dgm:t></dgm:pt>
  </dgm:ptLst>
  <dgm:cxnLst><dgm:cxn modelId="c1" type="parOf" srcId="n1" destId="n2"/></dgm:cxnLst>
</dgm:dataModel>"""


def _layout_xml() -> str:
    return f"""<dgm:layoutDef {NS}><dgm:catLst>
    <dgm:cat type="http://schemas.openxmlformats.org/drawingml/2006/diagram/process"/>
</dgm:catLst></dgm:layoutDef>"""
