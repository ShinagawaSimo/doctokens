"""Implicit cell addresses and masters after slaves are producer encodings that Excel does not reliably save. The
large selected-formula case awaits xlsx-formula-range-api.xlsx; malformed groups remain exceptions.
"""

import io
import zipfile
from xml.etree import ElementTree as ET

import pytest
from ooxml_llm_core.models import ParseResult
from xlsx_llm_parser import parse_xlsx

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"


def _source(sheets: dict[str, str]) -> bytes:
    sheet_nodes = "".join(f'<sheet name="{name}" sheetId="{index}" r:id="r{index}"/>' for index, name in enumerate(sheets, 1))
    sheet_rels = "".join(
        f'<Relationship Id="r{index}" Type="{REL}/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    entries = {
        "[Content_Types].xml": f'<Types xmlns="{CONTENT_TYPES}"><Default Extension="xml" ContentType="application/xml"/></Types>',
        "_rels/.rels": (
            f'<Relationships xmlns="{PACKAGE_REL}"><Relationship Id="r" Type="{REL}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>{sheet_nodes}</sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{PACKAGE_REL}">{sheet_rels}</Relationships>',
    }
    for index, sheet_xml in enumerate(sheets.values(), 1):
        entries[f"xl/worksheets/sheet{index}.xml"] = f'<worksheet xmlns="{MAIN}"><sheetData>{sheet_xml}</sheetData></worksheet>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def _cell(result: ParseResult) -> ET.Element:
    root = ET.fromstring(result.text)
    cell = root.find(".//grid/tr/cell")
    assert cell is not None
    return cell


def test_range_uses_left_master_and_implicit_slave_reference() -> None:
    source = _source(
        {
            "Data": (
                '<row r="1"><c r="A1"><f t="shared" ref="A1:B1" si="0">A1+1</f><v>2</v></c>'
                '<c><f t="shared" si="0"/><v>3</v></c></row>'
            )
        }
    )
    result = parse_xlsx(source, density="semantic", sheet="Data", range_spec="B1:B1")
    assert _cell(result).get("formula") == "B1+1"
    grid = ET.fromstring(result.text).find(".//grid")
    assert grid is not None and grid.get("ref") == "B1:B1"
    assert not result.report.warnings


def test_master_after_slave_and_sheet_scoped_indices() -> None:
    source = _source(
        {
            "Data": (
                '<row r="1"><c r="A1"><f t="shared" si="0"/><v>4</v></c></row>'
                '<row r="2"><c r="A2"><f t="shared" ref="A1:A2" si="0">B2*2</f><v>2</v></c></row>'
            ),
            "Other": (
                '<row r="1"><c r="A1"><f t="shared" ref="A1:A2" si="0">C1+3</f><v>4</v></c></row>'
                '<row r="2"><c r="A2"><f t="shared" si="0"/><v>5</v></c></row>'
            ),
        }
    )
    first = parse_xlsx(source, density="structural", sheet="Data", range_spec="A1:A1")
    second = parse_xlsx(source, density="structural", sheet="Other", range_spec="A2:A2")
    assert _cell(first).get("formula") == "B1*2"
    assert _cell(second).get("formula") == "C2+3"
    assert not first.report.warnings
    assert not second.report.warnings


@pytest.mark.parametrize(
    ("rows", "selected", "code"),
    [
        ('<row r="2"><c r="A2"><f t="shared" si="0"/><v>4</v></c></row>', "A2:A2", "SHARED_FORMULA_UNRESOLVED"),
        (
            '<row r="1"><c r="A1"><f t="shared" ref="A1:A2" si="0"/><v>2</v></c></row>'
            '<row r="2"><c r="A2"><f t="shared" si="0"/><v>4</v></c></row>',
            "A2:A2",
            "SHARED_FORMULA_UNRESOLVED",
        ),
        (
            '<row r="1"><c r="A1"><f t="shared" ref="bad" si="0">B1*2</f><v>2</v></c></row>'
            '<row r="2"><c r="A2"><f t="shared" si="0"/><v>4</v></c></row>',
            "A2:A2",
            "SHARED_FORMULA_INVALID",
        ),
        (
            '<row r="1"><c r="A1"><f t="shared" ref="A1:A2" si="0">B1*2</f><v>2</v></c></row>'
            '<row r="3"><c r="A3"><f t="shared" si="0"/><v>4</v></c></row>',
            "A3:A3",
            "SHARED_FORMULA_INVALID",
        ),
        (
            '<row r="1"><c r="A1"><f t="shared" ref="A1:A2" si="0">B1*2</f><v>2</v></c>'
            '<c r="C1"><f t="shared" ref="C1:C2" si="0">D1*2</f><v>2</v></c></row>'
            '<row r="2"><c r="A2"><f t="shared" si="0"/><v>4</v></c></row>',
            "A2:A2",
            "SHARED_FORMULA_INVALID",
        ),
    ],
)
def test_invalid_selected_group_retains_value_and_warns_once(rows: str, selected: str, code: str) -> None:
    result = parse_xlsx(_source({"Data": rows}), density="semantic", sheet="Data", range_spec=selected)
    assert _cell(result).text == "4"
    assert _cell(result).get("formula") is None
    assert [(item.code, item.locator) for item in result.report.warnings] == [
        (code, f"xl/worksheets/sheet1.xml!{selected.split(':')[0]}")
    ]


def test_many_out_of_range_values_do_not_enter_result() -> None:
    other_rows = "".join(f'<row r="{row}"><c r="B{row}"><v>{row}</v></c></row>' for row in range(3, 503))
    source = _source(
        {
            "Data": (
                '<row r="1"><c r="A1"><f t="shared" ref="A1:A2" si="0">B1*2</f><v>2</v></c></row>'
                '<row r="2"><c r="A2"><f t="shared" si="0"/><v>4</v></c></row>' + other_rows
            )
        }
    )
    result = parse_xlsx(source, density="structural", sheet="Data", range_spec="A2:A2")
    assert _cell(result).get("formula") == "B2*2"
    assert len(ET.fromstring(result.text).findall(".//grid/tr/cell")) == 1
