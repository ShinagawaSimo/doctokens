"""Invalid OOXML values, missing parts and extreme states unavailable through normal Office UI."""

from __future__ import annotations

from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from doctokens_excel import parse_xlsx

_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_P = "http://schemas.openxmlformats.org/package/2006/relationships"
_D = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
_XDA = "http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray"


def _package(sheet: str, extra: dict[str, str] | None = None, *, kind: str = "worksheet") -> bytes:
    # This is infrastructure for malformed/over-limit source conditions only.
    entries = {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>'
        ),
        "_rels/.rels": (
            f'<Relationships xmlns="{_P}"><Relationship Id="r" Type="{_R}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'<workbook xmlns="{_S}" xmlns:r="{_R}"><sheets><sheet name="Data" sheetId="1" r:id="s"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'<Relationships xmlns="{_P}"><Relationship Id="s" Type="{_R}/{kind}" '
            'Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": sheet,
    }
    entries.update(extra or {})
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def _equal_xml(actual: str, expected: str) -> None:
    assert ET.canonicalize(actual) == ET.canonicalize(expected)


@pytest.mark.parametrize("cm", ["-1", "bad", "99999999"])
def test_invalid_cell_metadata_reference_preserves_formula_and_cache(cm: str) -> None:
    # Invalid indices cannot be set in Excel's cell-format UI.
    source = _package(
        f'<worksheet xmlns="{_S}"><sheetData><row r="1"><c r="A1" cm="{cm}">'
        '<f t="array" ref="A1:A2" aca="1">ROW(A1:A2)</f><v>1</v></c></row>'
        '<row r="2"><c r="A2"><v>2</v></c></row></sheetData></worksheet>'
    )
    result = parse_xlsx(source, density="structural")
    assert "DYNAMIC_ARRAY_METADATA_UNRESOLVED" in [item.code for item in result.report.warnings]
    _equal_xml(
        result.text,
        '<workbook density="structural" format="xlsx"><sheet name="Data"><grid ref="A1:A2">'
        '<tr number="1"><cell formula="ROW(A1:A2)" formula-range="A1:A2" formula-type="array">1</cell></tr>'
        '<tr number="2"><cell>2</cell></tr></grid></sheet></workbook>',
    )


def test_extreme_array_range_does_not_materialize_a_worksheet_rectangle() -> None:
    # A full-sheet array with only two saved cells cannot be generated through a
    # normal successful spill (over 17 billion cells). Exercise bounded iteration.
    metadata = (
        f'<metadata xmlns="{_S}" xmlns:xda="{_XDA}"><metadataTypes><metadataType name="XLDAPR"/></metadataTypes>'
        '<futureMetadata name="XLDAPR"><bk><extLst><ext><xda:dynamicArrayProperties fDynamic="1"/>'
        '</ext></extLst></bk></futureMetadata><cellMetadata><bk><rc t="1" v="0"/></bk></cellMetadata></metadata>'
    )
    source = _package(
        f'<worksheet xmlns="{_S}"><sheetData><row r="1"><c r="A1" cm="1">'
        '<f t="array" ref="A1:XFD1048576">EXTREME()</f><v>1</v></c></row>'
        '<row r="1048576"><c r="XFD1048576"><v>2</v></c></row></sheetData></worksheet>',
        {"xl/metadata.xml": metadata},
    )
    result = parse_xlsx(source, density="structural")
    _equal_xml(
        result.text,
        '<workbook density="structural" format="xlsx"><sheet name="Data"><grid ref="A1:XFD1048576">'
        '<tr number="1"><cell formula="EXTREME()" formula-range="A1:XFD1048576" formula-type="array" '
        'spill-range="A1:XFD1048576">1</cell></tr>'
        '<tr number="1048576"><cell column="XFD" spill-from="A1">2</cell></tr></grid></sheet></workbook>',
    )


@pytest.mark.parametrize(
    ("declaration", "code", "expected"),
    [
        (
            '<dataValidations><dataValidation type="future" sqref="A1"/></dataValidations>',
            "DATA_VALIDATION_UNSUPPORTED",
            '<data-validation ref="A1" type="future"><unsupported type="data-validation"/></data-validation>',
        ),
        (
            '<conditionalFormatting sqref="A1"><cfRule type="future" priority="1"/></conditionalFormatting>',
            "CONDITIONAL_FORMAT_UNSUPPORTED",
            '<conditional-format ref="A1"><rule priority="1" type="future">'
            '<unsupported type="conditional-format"/></rule></conditional-format>',
        ),
    ],
)
def test_unknown_rule_types_keep_element_placeholders(declaration: str, code: str, expected: str) -> None:
    source = _package(f'<worksheet xmlns="{_S}"><sheetData/>{declaration}</worksheet>')
    result = parse_xlsx(source, density="semantic")
    assert code in [item.code for item in result.report.warnings]
    _equal_xml(result.text, f'<workbook density="semantic" format="xlsx"><sheet name="Data">{expected}</sheet></workbook>')


def test_invalid_validation_boolean_keeps_the_readable_rule_without_a_placeholder() -> None:
    source = _package(
        f'<worksheet xmlns="{_S}"><sheetData/><dataValidations>'
        '<dataValidation type="list" sqref="A1" allowBlank="invalid"><formula1>"A,B"</formula1></dataValidation>'
        "</dataValidations></worksheet>"
    )
    result = parse_xlsx(source, density="structural")
    assert "RULE_BOOLEAN_INVALID" in [item.code for item in result.report.warnings]
    _equal_xml(
        result.text,
        '<workbook density="structural" format="xlsx"><sheet name="Data">'
        '<data-validation formula1="&quot;A,B&quot;" ref="A1" type="list"/></sheet></workbook>',
    )


@pytest.mark.parametrize("body", ["<broken", f'<chartsheet xmlns="{_S}"/>'])
def test_unreadable_chart_sheet_keeps_its_existence(body: str) -> None:
    source = _package(body, kind="chartsheet")
    result = parse_xlsx(source, density="structural")
    assert "CHART_SHEET_UNREADABLE" in [item.code for item in result.report.warnings]
    _equal_xml(
        result.text,
        '<workbook density="structural" format="xlsx"><chart-sheet name="Data">'
        '<unsupported id="shape1" source="chart-sheet" type="drawing"/></chart-sheet></workbook>',
    )


def test_missing_drawing_part_retains_its_placeholder() -> None:
    source = _package(
        f'<worksheet xmlns="{_S}"><sheetData/></worksheet>',
        {
            "xl/worksheets/_rels/sheet1.xml.rels": (
                f'<Relationships xmlns="{_P}"><Relationship Id="d" Type="{_R}/drawing" '
                'Target="../drawings/missing.xml"/></Relationships>'
            ),
        },
    )
    result = parse_xlsx(source, density="structural")
    assert "DRAWING_PART_MISSING" in [item.code for item in result.report.warnings]
    _equal_xml(
        result.text,
        '<workbook density="structural" format="xlsx"><sheet name="Data">'
        '<unsupported id="shape1" source="drawing" type="drawing"/></sheet></workbook>',
    )


def test_invalid_anchor_does_not_hide_readable_drawing_text() -> None:
    source = _package(
        f'<worksheet xmlns="{_S}"><sheetData/></worksheet>',
        {
            "xl/worksheets/_rels/sheet1.xml.rels": (
                f'<Relationships xmlns="{_P}"><Relationship Id="d" Type="{_R}/drawing" '
                'Target="../drawings/d.xml"/></Relationships>'
            ),
            "xl/drawings/d.xml": f'<wsDr xmlns="{_D}" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            "<twoCellAnchor><from><col>invalid</col><row>-1</row></from><sp><txBody><a:p><a:r><a:t>Keep</a:t></a:r>"
            "</a:p></txBody></sp></twoCellAnchor></wsDr>",
        },
    )
    result = parse_xlsx(source, density="structural")
    assert "DRAWING_ANCHOR_INVALID" in [item.code for item in result.report.warnings]
    _equal_xml(
        result.text,
        '<workbook density="structural" format="xlsx"><sheet name="Data">'
        '<textbox id="shape1"><p>Keep</p></textbox></sheet></workbook>',
    )
