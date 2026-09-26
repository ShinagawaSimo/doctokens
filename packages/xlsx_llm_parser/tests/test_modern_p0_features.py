"""Regression coverage for Excel rich values, cell controls, and pivot context."""

import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

from ooxml_llm_core.package import PackageError
from xlsx_llm_parser import open_xlsx, parse_xlsx
from xlsx_llm_parser import parse_xlsx as parse_xlsx_result

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_RP = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_XLRD = "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata"
NS_FPB = "http://schemas.microsoft.com/office/spreadsheetml/2022/featurepropertybag"


def _make_xlsx(entries: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


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
        plain = parse_xlsx(data, density="plain").text
        structural = parse_xlsx(data, density="structural").text
        semantic = parse_xlsx(data, density="semantic").text

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

    def test_optional_catalog_xml_failures_are_local_and_reported(self) -> None:
        cases = (
            ("xl/metadata.xml", "#VALUE!", "checkbox", "Region"),
            ("xl/richData/rdrichvalue.xml", "#VALUE!", "checkbox", "Region"),
            ("xl/richData/rdrichvaluestructure.xml", "#VALUE!", "checkbox", "Region"),
            ("xl/richData/webImages.xml", "Logo", "checkbox", "Region"),
            ("xl/featurePropertyBag/featurePropertyBag.xml", "Logo", None, "Region"),
            ("xl/pivotCache/pivotCacheDefinition1.xml", "Logo", "checkbox", "0"),
            ("xl/pivotTables/pivotTable1.xml", "Logo", "checkbox", None),
            ("xl/slicerCaches/slicerCache1.xml", "Logo", "checkbox", "Region"),
            ("xl/timelineCaches/timelineCache1.xml", "Logo", "checkbox", "Region"),
        )
        for part, first_text, control, row_field in cases:
            with self.subTest(part=part):
                entries = _base_entries()
                entries[part] = "<broken"
                source = _make_xlsx(entries)
                for density in ("plain", "structural", "semantic"):
                    result = parse_xlsx_result(source, density=density)
                    self.assertEqual(
                        [(warning.code, warning.locator) for warning in result.report.warnings],
                        [("XLSX_CATALOG_XML_INVALID", part)],
                    )
                    self.assertIn(first_text, result.text)
                    self.assertIn("true", result.text)
                root = ET.fromstring(parse_xlsx_result(source, density="semantic").text)
                checkbox = root.find(".//cell[@control]")
                self.assertEqual(checkbox.get("control") if checkbox is not None else None, control)
                pivot = root.find(".//pivot-table")
                self.assertEqual(pivot.get("rows") if pivot is not None else None, row_field)

    def test_optional_relationship_errors_keep_cells_and_other_catalogs(self) -> None:
        cases = (
            ("xl/richData/_rels/richValueRel.xml.rels", "<broken", "XLSX_CATALOG_RELS_INVALID"),
            (
                "xl/richData/_rels/richValueRel.xml.rels",
                f'<Relationships xmlns="{NS_RP}"><Relationship Id="rImage" Type="{NS_O}/image"/></Relationships>',
                "XLSX_CATALOG_RELS_INVALID",
            ),
            ("xl/richData/_rels/webImages.xml.rels", "<broken", "XLSX_CATALOG_RELS_INVALID"),
        )
        for part, broken, code in cases:
            with self.subTest(part=part, broken=broken):
                entries = _base_entries()
                if "webImages" in part:
                    entries["xl/richData/webImages.xml"] = (
                        f'<webImages xmlns:r="{NS_O}"><webImage><address r:id="rWeb"/></webImage></webImages>'
                    )
                entries[part] = broken
                source = _make_xlsx(entries)
                with open_xlsx(source) as session:
                    first = session.render(density="semantic")
                    second = session.render(density="semantic")
                self.assertEqual(first.text, second.text)
                self.assertEqual([(w.code, w.locator) for w in first.report.warnings], [(code, part)])
                root = ET.fromstring(first.text)
                self.assertEqual(root.find(".//cell").text, "Logo")
                self.assertEqual(root.find(".//cell[@control]").get("control"), "checkbox")
                self.assertEqual(root.find(".//pivot-table").get("rows"), "Region")

    def test_optional_reference_failures_and_absence_are_distinct(self) -> None:
        base = _base_entries()
        cases = (
            ("xl/media/logo.png", "XLSX_CATALOG_PART_MISSING", "xl/media/logo.png"),
            (
                "xl/richData/_rels/richValueRel.xml.rels",
                "XLSX_CATALOG_PART_MISSING",
                "xl/richData/_rels/richValueRel.xml.rels",
            ),
            ("xl/pivotCache/pivotCacheDefinition1.xml", "XLSX_CATALOG_PART_MISSING", "xl/pivotCache/pivotCacheDefinition1.xml"),
            ("xl/pivotTables/pivotTable1.xml", "XLSX_CATALOG_PART_MISSING", "xl/pivotTables/pivotTable1.xml"),
        )
        for part, code, locator in cases:
            with self.subTest(part=part):
                entries = dict(base)
                entries.pop(part)
                result = parse_xlsx_result(_make_xlsx(entries), density="semantic")
                self.assertIn((code, locator), [(warning.code, warning.locator) for warning in result.report.warnings])
                self.assertIn("true", result.text)
        missing_metadata = dict(base)
        missing_metadata.pop("xl/metadata.xml")
        missing_metadata["xl/worksheets/sheet1.xml"] = missing_metadata["xl/worksheets/sheet1.xml"].replace(
            '<c r="B1"', '<c r="C1" t="e" vm="1"><v>#VALUE!</v></c><c r="B1"'
        )
        result = parse_xlsx_result(_make_xlsx(missing_metadata), density="semantic")
        self.assertEqual(
            [(warning.code, warning.locator) for warning in result.report.warnings],
            [("XLSX_CATALOG_PART_MISSING", "xl/metadata.xml")],
        )
        unresolved = dict(base)
        unresolved["xl/richData/richValueRel.xml"] = unresolved["xl/richData/richValueRel.xml"].replace(
            'r:id="rImage"', 'r:id="missing"'
        )
        result = parse_xlsx_result(_make_xlsx(unresolved), density="semantic")
        self.assertIn(
            ("XLSX_CATALOG_REFERENCE_UNRESOLVED", "xl/richData/richValueRel.xml"),
            [(warning.code, warning.locator) for warning in result.report.warnings],
        )
        invalid_index = dict(base)
        invalid_index["xl/metadata.xml"] = invalid_index["xl/metadata.xml"].replace('rvb i="0"', 'rvb i="99"')
        result = parse_xlsx_result(_make_xlsx(invalid_index), density="semantic")
        self.assertIn(
            ("XLSX_CATALOG_REFERENCE_UNRESOLVED", "xl/metadata.xml"),
            [(warning.code, warning.locator) for warning in result.report.warnings],
        )
        missing_bags = dict(base)
        missing_bags.pop("xl/featurePropertyBag/featurePropertyBag.xml")
        result = parse_xlsx_result(_make_xlsx(missing_bags), density="semantic")
        self.assertIn(
            ("XLSX_CATALOG_REFERENCE_UNRESOLVED", "xl/styles.xml"),
            [(warning.code, warning.locator) for warning in result.report.warnings],
        )
        bare = dict(base)
        bare["xl/workbook.xml"] = bare["xl/workbook.xml"].replace(
            '<pivotCaches><pivotCache cacheId="7" r:id="rCache"/></pivotCaches>', ""
        )
        bare["xl/worksheets/sheet1.xml"] = bare["xl/worksheets/sheet1.xml"].replace(' vm="1"', "")
        bare["xl/styles.xml"] = bare["xl/styles.xml"].replace('<fpb:xfComplement i="0"/>', "")
        for part in list(bare):
            if part.startswith(
                (
                    "xl/richData/",
                    "xl/featurePropertyBag/",
                    "xl/pivotCache/",
                    "xl/pivotTables/",
                    "xl/slicerCaches/",
                    "xl/timelineCaches/",
                )
            ):
                bare.pop(part)
        bare.pop("xl/metadata.xml")
        bare.pop("xl/worksheets/_rels/sheet1.xml.rels")
        result = parse_xlsx_result(_make_xlsx(bare), density="semantic")
        self.assertEqual(result.report.warnings, ())

    def test_required_parts_still_fail(self) -> None:
        for part in ("xl/workbook.xml", "xl/worksheets/sheet1.xml"):
            with self.subTest(part=part):
                entries = _base_entries()
                entries.pop(part)
                with self.assertRaises(PackageError):
                    parse_xlsx_result(_make_xlsx(entries), density="semantic")


if __name__ == "__main__":
    unittest.main()
