"""Workbook-scoped resource id tests."""

import io
import unittest
import zipfile
from pathlib import Path

from test_support.api_v2_text import parse_xlsx
from test_support.file_contract import materialize_bytes

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _make_xlsx(entries: dict[str, str | bytes]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="resource-ids")


def _content_types() -> str:
    return (
        f'<Types xmlns="{NS_CT}">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType='
        '"application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.sheet.main+xml"/>'
        "</Types>"
    )


def _root_rels() -> str:
    return (
        f'<Relationships xmlns="{NS_RP}">'
        f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml() -> str:
    return (
        f'<workbook xmlns="{NS_S}" xmlns:r="{NS_O}">'
        "<sheets>"
        '<sheet name="First" sheetId="1" r:id="rSheet1"/>'
        '<sheet name="Second" sheetId="2" r:id="rSheet2"/>'
        "</sheets>"
        "</workbook>"
    )


def _workbook_rels() -> str:
    return (
        f'<Relationships xmlns="{NS_RP}">'
        f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        f'<Relationship Id="rSheet2" Type="{NS_O}/worksheet" '
        'Target="worksheets/sheet2.xml"/>'
        "</Relationships>"
    )


def _sheet_xml(label: str) -> str:
    return (
        f'<worksheet xmlns="{NS_S}">'
        "<sheetData>"
        '<row r="1">'
        f'<c r="A1" t="inlineStr"><is><t>{label}</t></is></c>'
        "</row>"
        "</sheetData>"
        "</worksheet>"
    )


def _sheet_rels(sheet_index: int) -> str:
    return (
        f'<Relationships xmlns="{NS_RP}">'
        f'<Relationship Id="rTable{sheet_index}" Type="{NS_O}/table" '
        f'Target="../tables/table{sheet_index}.xml"/>'
        f'<Relationship Id="rDraw{sheet_index}" Type="{NS_O}/drawing" '
        f'Target="../drawings/drawing{sheet_index}.xml"/>'
        f'<Relationship Id="rPivot{sheet_index}" Type="{NS_O}/pivotTable" '
        f'Target="../pivotTables/pivotTable{sheet_index}.xml"/>'
        "</Relationships>"
    )


def _table_xml(sheet_index: int) -> str:
    return (
        f'<table xmlns="{NS_S}" '
        f'name="Sales{sheet_index}" displayName="Sales{sheet_index}" ref="A1:B2">'
        '<tableColumns count="2">'
        '<tableColumn name="Name"/>'
        '<tableColumn name="Value"/>'
        "</tableColumns>"
        "</table>"
    )


def _drawing_rels(sheet_index: int) -> str:
    return (
        f'<Relationships xmlns="{NS_RP}">'
        f'<Relationship Id="rImg{sheet_index}" Type="{NS_O}/image" '
        f'Target="../media/image{sheet_index}.png"/>'
        f'<Relationship Id="rChart{sheet_index}" Type="{NS_O}/chart" '
        f'Target="../charts/chart{sheet_index}.xml"/>'
        "</Relationships>"
    )


def _drawing_xml(sheet_index: int) -> str:
    return (
        f'<wsDr xmlns="{NS_XDR}" xmlns:a="{NS_A}" xmlns:c="{NS_C}" '
        f'xmlns:r="{NS_O}">'
        "<twoCellAnchor>"
        "<from><col>0</col><row>0</row></from>"
        "<to><col>2</col><row>1</row></to>"
        "<pic>"
        f'<blipFill><a:blip r:embed="rImg{sheet_index}"/></blipFill>'
        "</pic>"
        "<graphicFrame>"
        f'<c:chart r:id="rChart{sheet_index}"/>'
        "</graphicFrame>"
        "</twoCellAnchor>"
        "</wsDr>"
    )


class WorkbookResourceIdTests(unittest.TestCase):
    def test_resource_ids_do_not_restart_on_each_sheet(self) -> None:
        data = _make_xlsx(
            {
                "[Content_Types].xml": _content_types(),
                "_rels/.rels": _root_rels(),
                "xl/workbook.xml": _workbook_xml(),
                "xl/_rels/workbook.xml.rels": _workbook_rels(),
                "xl/worksheets/sheet1.xml": _sheet_xml("First"),
                "xl/worksheets/sheet2.xml": _sheet_xml("Second"),
                "xl/worksheets/_rels/sheet1.xml.rels": _sheet_rels(1),
                "xl/worksheets/_rels/sheet2.xml.rels": _sheet_rels(2),
                "xl/tables/table1.xml": _table_xml(1),
                "xl/tables/table2.xml": _table_xml(2),
                "xl/drawings/drawing1.xml": _drawing_xml(1),
                "xl/drawings/drawing2.xml": _drawing_xml(2),
                "xl/drawings/_rels/drawing1.xml.rels": _drawing_rels(1),
                "xl/drawings/_rels/drawing2.xml.rels": _drawing_rels(2),
                "xl/media/image1.png": b"",
                "xl/media/image2.png": b"",
            },
        )

        structural = parse_xlsx(data, density="structural")

        self.assertIn('<table-summary id="table-0" name="Sales1" ref="A1:B2" />', structural)
        self.assertIn('<table-summary id="table-1" name="Sales2" ref="A1:B2" />', structural)
        self.assertIn('<img id="image1" ref="A1" />', structural)
        self.assertIn('<img id="image2" ref="A1" />', structural)
        self.assertIn('<chart id="chart1" ref="A1"', structural)
        self.assertIn('<chart id="chart2" ref="A1"', structural)
        self.assertIn('<pivot-table id="pivot1"', structural)
        self.assertIn('<pivot-table id="pivot2"', structural)


if __name__ == "__main__":
    unittest.main()
