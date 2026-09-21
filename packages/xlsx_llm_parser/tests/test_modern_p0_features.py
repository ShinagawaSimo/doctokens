"""Regression coverage for Excel rich values, cell controls, and pivot context."""

import io
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from test_support.api_v2_text import parse_xlsx
from test_support.file_contract import materialize_bytes

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_XLRD = "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata"
NS_FPB = "http://schemas.microsoft.com/office/spreadsheetml/2022/featurepropertybag"


def _make_xlsx(entries: dict[str, str | bytes]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="modern-features")


def _base_entries() -> dict[str, str]:
    return {
        "[Content_Types].xml": (
            f'<Types xmlns="{NS_CT}">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'<Relationships xmlns="{NS_RP}">'
            f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            f'<workbook xmlns="{NS_S}" xmlns:r="{NS_O}">'
            '<sheets><sheet name="Data" sheetId="1" r:id="rSheet"/></sheets>'
            '<pivotCaches><pivotCache cacheId="7" r:id="rCache"/></pivotCaches>'
            "</workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            f'<Relationships xmlns="{NS_RP}">'
            f'<Relationship Id="rSheet" Type="{NS_O}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rCache" Type="{NS_O}/pivotCacheDefinition" Target="pivotCache/pivotCacheDefinition1.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{NS_S}"><sheetData>'
            '<row r="1"><c r="A1" t="e" vm="1"><v>#VALUE!</v></c>'
            '<c r="B1" t="b" s="1"><v>1</v></c></row>'
            "</sheetData></worksheet>"
        ),
        "xl/styles.xml": (
            f'<styleSheet xmlns="{NS_S}" xmlns:fpb="{NS_FPB}">'
            '<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="0">'
            '<extLst><ext><fpb:xfComplement i="0"/></ext></extLst>'
            "</xf></cellXfs></styleSheet>"
        ),
        "xl/featurePropertyBag/featurePropertyBag.xml": (
            f'<fpb:FeaturePropertyBags xmlns:fpb="{NS_FPB}">'
            '<fpb:bag type="Checkbox"><fpb:i k="default">2</fpb:i></fpb:bag>'
            '<fpb:bag type="XFControls"><fpb:bagId k="CellControl">0</fpb:bagId></fpb:bag>'
            '<fpb:bag type="XFComplement"><fpb:bagId k="XFControls">1</fpb:bagId></fpb:bag>'
            '<fpb:bag type="XFComplements"><fpb:a k="MappedFeaturePropertyBags"><fpb:bagId>2</fpb:bagId></fpb:a></fpb:bag>'
            "</fpb:FeaturePropertyBags>"
        ),
        "xl/metadata.xml": (
            f'<metadata xmlns="{NS_S}" xmlns:xlrd="{NS_XLRD}">'
            '<metadataTypes><metadataType name="XLRICHVALUE"/></metadataTypes>'
            '<futureMetadata name="XLRICHVALUE"><bk><extLst><ext><xlrd:rvb i="0"/></ext></extLst></bk></futureMetadata>'
            '<valueMetadata><bk><rc t="1" v="0"/></bk></valueMetadata>'
            "</metadata>"
        ),
        "xl/richData/rdrichvaluestructure.xml": (
            f'<rvStructures xmlns="{NS_XLRD}"><s t="_localImage">'
            '<k n="_rvRel:LocalImageIdentifier" t="i"/><k n="Text" t="s"/>'
            "</s></rvStructures>"
        ),
        "xl/richData/rdrichvalue.xml": (f'<rvData xmlns="{NS_XLRD}"><rv s="0"><v>0</v><v>Logo</v></rv></rvData>'),
        "xl/richData/richValueRel.xml": (f'<richValueRel xmlns="{NS_XLRD}" xmlns:r="{NS_O}"><rel r:id="rImage"/></richValueRel>'),
        "xl/richData/_rels/richValueRel.xml.rels": (
            f'<Relationships xmlns="{NS_RP}">'
            f'<Relationship Id="rImage" Type="{NS_O}/image" Target="../media/logo.png"/>'
            "</Relationships>"
        ),
        "xl/media/logo.png": b"png",
        "xl/pivotCache/pivotCacheDefinition1.xml": (
            f'<pivotCacheDefinition xmlns="{NS_S}" refreshOnLoad="1" recordCount="12">'
            '<cacheSource><worksheetSource sheet="Data" ref="A1:B12"/></cacheSource>'
            '<cacheFields count="2"><cacheField name="Region"/><cacheField name="Amount"/></cacheFields>'
            "</pivotCacheDefinition>"
        ),
        "xl/worksheets/_rels/sheet1.xml.rels": (
            f'<Relationships xmlns="{NS_RP}">'
            f'<Relationship Id="rPivot" Type="{NS_O}/pivotTable" Target="../pivotTables/pivotTable1.xml"/>'
            "</Relationships>"
        ),
        "xl/pivotTables/pivotTable1.xml": (
            f'<pivotTableDefinition xmlns="{NS_S}" name="SalesPivot" cacheId="7">'
            '<location ref="D1:E5"/><rowFields><field x="0"/></rowFields>'
            '<dataFields><dataField name="Sum of Amount" fld="1"/></dataFields>'
            "</pivotTableDefinition>"
        ),
        "xl/slicerCaches/slicerCache1.xml": (
            '<slicerCacheDefinition name="RegionFilter" sourceName="Region">'
            '<slicerCacheData><tabularSlicerCache pivotCacheId="7"/></slicerCacheData>'
            "</slicerCacheDefinition>"
        ),
        "xl/timelineCaches/timelineCache1.xml": (
            '<timelineCacheDefinition name="DateFilter" sourceName="Date" pivotCacheId="7">'
            '<timelineState level="months"/></timelineCacheDefinition>'
        ),
    }


class ModernP0FeatureTests(unittest.TestCase):
    def test_rich_value_checkbox_and_pivot_context(self) -> None:
        data = _make_xlsx(_base_entries())
        plain = parse_xlsx(data, density="plain")
        structural = parse_xlsx(data, density="structural")
        semantic = parse_xlsx(data, density="semantic")

        self.assertIn("Logo", plain)
        self.assertIn("[Checkbox true]", plain)
        structural_root = ET.fromstring(structural)
        semantic_root = ET.fromstring(semantic)
        self.assertEqual(structural_root.find(".//cell").get("in-cell-image"), "true")
        self.assertEqual(structural_root.find(".//cell[@control]").get("control"), "checkbox")
        self.assertEqual(semantic_root.find("pivot-cache").get("id"), "cache1")
        self.assertEqual(semantic_root.find("slicer").get("name"), "RegionFilter")
        self.assertEqual(semantic_root.find("timeline").get("level"), "months")
        pivot = semantic_root.find(".//pivot-table")
        self.assertEqual(pivot.get("id"), "pivot1")
        self.assertEqual(pivot.get("rows"), "Region")
        self.assertEqual(pivot.get("values"), "Sum of Amount")


if __name__ == "__main__":
    unittest.main()
