"""Semantic equivalence across parser entry points and densities."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from docx_llm_parser import open_docx, parse_docx
from pptx_llm_parser import open_pptx, parse_pptx
from xlsx_llm_parser import open_xlsx, parse_xlsx

from test_support.content_events import (
    extract_object_events,
    extract_page_events,
    extract_reference_events,
    extract_text_events,
    extract_warning_events,
)

ROOT = Path(__file__).parents[3]
DOCX = ROOT / "test_support" / "fixtures" / "docx" / "docx-heading-style.docx"


def _source_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _xlsx_source() -> bytes:
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    content_types = "http://schemas.openxmlformats.org/package/2006/content-types"
    entries = {
        "[Content_Types].xml": f'<Types xmlns="{content_types}"><Default Extension="xml" ContentType="application/xml"/></Types>',
        "_rels/.rels": (
            f'<Relationships xmlns="{package_rel}"><Relationship Id="r" Type="{rel}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets><sheet name="Data" sheetId="1" r:id="r1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'<Relationships xmlns="{package_rel}"><Relationship Id="r1" Type="{rel}/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{main}"><sheetData><row r="1">'
            '<c r="A1" t="inlineStr"><is><t>First</t></is></c><c r="C1"><f>1+2</f><v>3</v></c></row>'
            '<row r="3" hidden="1"><c r="B3" t="inlineStr"><is><t>Last</t></is></c></row>'
            "</sheetData></worksheet>"
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _pptx_source() -> bytes:
    presentation = "http://schemas.openxmlformats.org/presentationml/2006/main"
    drawing = "http://schemas.openxmlformats.org/drawingml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    content_types = "http://schemas.openxmlformats.org/package/2006/content-types"
    shapes = "".join(
        f'<p:sp><p:nvSpPr><p:cNvPr id="{index}" name="Shape {index}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="0" y="{y}"/><a:ext cx="1000" cy="1000"/></a:xfrm></p:spPr>'
        f"<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{label}</a:t></a:r></a:p></p:txBody></p:sp>"
        for index, label, y in ((2, "First", 3000), (3, "Second", 0))
    )
    entries = {
        "[Content_Types].xml": f'<Types xmlns="{content_types}"><Default Extension="xml" ContentType="application/xml"/></Types>',
        "_rels/.rels": (
            f'<Relationships xmlns="{package_rel}"><Relationship Id="r" Type="{rel}/officeDocument" '
            'Target="ppt/presentation.xml"/></Relationships>'
        ),
        "ppt/presentation.xml": (
            f'<p:presentation xmlns:p="{presentation}" xmlns:r="{rel}"><p:sldIdLst>'
            '<p:sldId id="256" r:id="r1"/></p:sldIdLst>'
            '<p:sldSz cx="12192000" cy="6858000"/></p:presentation>'
        ),
        "ppt/_rels/presentation.xml.rels": (
            f'<Relationships xmlns="{package_rel}"><Relationship Id="r1" Type="{rel}/slide" '
            'Target="slides/slide1.xml"/></Relationships>'
        ),
        "ppt/slides/slide1.xml": (
            f'<p:sld xmlns:p="{presentation}" xmlns:a="{drawing}"><p:cSld><p:spTree>'
            f"<p:nvGrpSpPr/><p:grpSpPr/>{shapes}</p:spTree></p:cSld></p:sld>"
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_docx_path_bytes_session_events_agree() -> None:
    for density in ("structural", "semantic"):
        path_result = parse_docx(DOCX, density=density)
        bytes_result = parse_docx(_source_bytes(DOCX), density=density)
        with open_docx(DOCX) as session:
            session_result = session.render(density=density)
        for result in (bytes_result, session_result):
            assert extract_text_events(path_result.text, "docx") == extract_text_events(result.text, "docx")
            assert extract_page_events(path_result.text) == extract_page_events(result.text)
            assert extract_reference_events(path_result.text) == extract_reference_events(result.text)
            assert extract_object_events(path_result.text) == extract_object_events(result.text)
            assert extract_warning_events(path_result.report.warnings) == extract_warning_events(result.report.warnings)
    page_lists = [extract_page_events(parse_docx(DOCX, density=density).text) for density in ("structural", "semantic")]
    assert page_lists[0] == page_lists[1]


def test_pptx_path_bytes_session_events_agree(tmp_path: Path) -> None:
    source = _pptx_source()
    path = tmp_path / "order.pptx"
    path.write_bytes(source)
    for density in ("structural", "semantic"):
        path_result = parse_pptx(path, density=density)
        bytes_result = parse_pptx(source, density=density)
        with open_pptx(path) as session:
            session_result = session.render(density=density)
        for result in (bytes_result, session_result):
            assert extract_text_events(path_result.text, "pptx") == extract_text_events(result.text, "pptx")
            assert extract_reference_events(path_result.text) == extract_reference_events(result.text)
            assert extract_object_events(path_result.text) == extract_object_events(result.text)
            if result is bytes_result or density == "semantic":
                assert extract_warning_events(path_result.report.warnings) == extract_warning_events(result.report.warnings)
        assert extract_text_events(path_result.text, "pptx") == [("1", "First"), ("1", "Second")]


def test_xlsx_sparse_cell_events_agree_across_entries(tmp_path: Path) -> None:
    source = _xlsx_source()
    path = tmp_path / "sparse.xlsx"
    path.write_bytes(source)
    for density in ("structural", "semantic"):
        result = parse_xlsx(source, density=density)
        path_result = parse_xlsx(path, density=density)
        with open_xlsx(path) as session:
            rendered = session.render(density=density)
        for other in (path_result, rendered):
            assert extract_text_events(result.text, "xlsx") == extract_text_events(other.text, "xlsx")
            assert extract_warning_events(result.report.warnings) == extract_warning_events(other.report.warnings)
        assert 'formula="1+2"' in result.text
        assert 'column="C"' in result.text
    assert extract_text_events(result.text, "xlsx") == [("Data", "First"), ("Data", "3"), ("Data", "Last")]
