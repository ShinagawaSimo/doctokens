"""Static style tests — bold, italic, color, fill in semantic density."""

import io
import unittest
import zipfile
from pathlib import Path

from xlsx_llm_parser import parse_xlsx

from test_support.file_contract import materialize_bytes

NS_S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _make_xlsx(entries: dict[str, str]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return materialize_bytes(buf.getvalue(), suffix=".xlsx", package="xlsx", name="styles")


class StyleTests(unittest.TestCase):
    def test_bold_detected(self) -> None:
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/styles.xml": (
                    f'<styleSheet xmlns="{NS_S}">'
                    '<fonts count="1">'
                    '<font><b/><color rgb="FFFF0000"/></font>'  # alpha=FF, RGB=FF0000
                    "</fonts>"
                    '<fills count="1"><fill><patternFill/></fill></fills>'
                    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0"/></cellXfs>'
                    "</styleSheet>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" s="0" t="inlineStr"><is><t>Bold</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        structural = parse_xlsx(data, density="structural")
        semantic = parse_xlsx(data, density="semantic")
        self.assertNotIn("bold", structural)
        self.assertIn("bold", semantic)
        self.assertIn("color=#FF0000", semantic)

    def test_fill_detected(self) -> None:
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/styles.xml": (
                    f'<styleSheet xmlns="{NS_S}">'
                    '<fonts count="1"><font/></fonts>'
                    '<fills count="1">'
                    '<fill><patternFill><fgColor rgb="FFFFFF00"/></patternFill></fill>'
                    "</fills>"
                    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0"/></cellXfs>'
                    "</styleSheet>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" s="0" t="inlineStr"><is><t>Yellow</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        self.assertIn("fill=#FFFF00", semantic)

    def test_no_styles_file(self) -> None:
        """Missing styles.xml should not crash style output."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" s="0" t="inlineStr"><is><t>Hi</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        self.assertIn("Hi", semantic)
        self.assertNotIn("bold", semantic)

    def test_theme_font_color_resolved(self) -> None:
        """Font colour specified via theme accent2 → resolved to RGB."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                # Theme file: accent2=ED7D31 (orange)
                "xl/theme/theme1.xml": (
                    '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                    "<a:themeElements>"
                    '<a:clrScheme name="Office">'
                    '<a:dk1><a:srgbClr val="000000"/></a:dk1>'
                    '<a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
                    '<a:dk2><a:srgbClr val="44546A"/></a:dk2>'
                    '<a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>'
                    '<a:accent1><a:srgbClr val="4472C4"/></a:accent1>'
                    '<a:accent2><a:srgbClr val="ED7D31"/></a:accent2>'
                    '<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>'
                    '<a:accent4><a:srgbClr val="FFC000"/></a:accent4>'
                    '<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5>'
                    '<a:accent6><a:srgbClr val="70AD47"/></a:accent6>'
                    '<a:hlink><a:srgbClr val="0563C1"/></a:hlink>'
                    '<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>'
                    "</a:clrScheme>"
                    "</a:themeElements>"
                    "</a:theme>"
                ),
                "xl/styles.xml": (
                    f'<styleSheet xmlns="{NS_S}">'
                    '<fonts count="1">'
                    # theme=5 → accent2 → #ED7D31
                    '<font><color theme="5"/></font>'
                    "</fonts>"
                    '<fills count="1"><fill><patternFill/></fill></fills>'
                    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0"/></cellXfs>'
                    "</styleSheet>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" s="0" t="inlineStr"><is><t>Orange</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        self.assertIn("color=#ED7D31", semantic)

    def test_default_theme_text_color_omitted(self) -> None:
        """theme=1 is default dark text in SpreadsheetML and should not add noise."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/styles.xml": (
                    f'<styleSheet xmlns="{NS_S}">'
                    '<fonts count="1"><font><color theme="1"/></font></fonts>'
                    '<fills count="1"><fill><patternFill/></fill></fills>'
                    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0"/></cellXfs>'
                    "</styleSheet>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" s="0" t="inlineStr"><is><t>Default black</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        self.assertIn("Default black", semantic)
        self.assertNotIn("color=", semantic)
        self.assertNotIn("#FFFFFF", semantic)

    def test_theme_fill_color_resolved(self) -> None:
        """Fill colour via theme accent4 with tint → resolved to tinted RGB."""
        data = _make_xlsx(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{NS_CT}">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Default Extension="rels" ContentType='
                    '"application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet.main+xml"/>'
                    "</Types>"
                ),
                "_rels/.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="r1" Type="{NS_O}/officeDocument" Target="xl/workbook.xml"/>'
                    "</Relationships>"
                ),
                "xl/workbook.xml": (
                    f'<workbook xmlns="{NS_S}" '
                    'xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                    "<sheets>"
                    '<sheet name="Data" sheetId="1" r:id="rSheet1"/>'
                    "</sheets>"
                    "</workbook>"
                ),
                "xl/_rels/workbook.xml.rels": (
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rSheet1" Type="{NS_O}/worksheet" '
                    'Target="worksheets/sheet1.xml"/>'
                    "</Relationships>"
                ),
                "xl/styles.xml": (
                    f'<styleSheet xmlns="{NS_S}">'
                    '<fonts count="1"><font/></fonts>'
                    '<fills count="1">'
                    # theme=7 → accent4 → FFC000, tint=0.8 → lighten
                    '<fill><patternFill><fgColor theme="7" tint="0.8"/></patternFill></fill>'
                    "</fills>"
                    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0"/></cellXfs>'
                    "</styleSheet>"
                ),
                "xl/worksheets/sheet1.xml": (
                    f'<worksheet xmlns="{NS_S}"><sheetData>'
                    '<row r="1"><c r="A1" s="0" t="inlineStr"><is><t>Tinted</t></is></c></row>'
                    "</sheetData></worksheet>"
                ),
            },
        )
        semantic = parse_xlsx(data, density="semantic")
        # accent4=FFC000 (gold), tint=0.8 lightens toward white
        # Expected: each channel: c' = c*(1-0.8) + 255*0.8
        # R: 0xFF=255 → 255*0.2 + 255*0.8 = 51+204 = 255=FF
        # G: 0xC0=192 → 192*0.2 + 255*0.8 = 38.4+204 = 242.4 → F2
        # B: 0x00=0 → 0*0.2 + 255*0.8 = 0+204 = 204=CC
        self.assertIn("fill=#FFF2CC", semantic)


if __name__ == "__main__":
    unittest.main()
