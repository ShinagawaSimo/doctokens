"""pptx templates."""

from __future__ import annotations

from _pptx_namespaces import A_NS, P_NS, R_NS


def theme_xml() -> str:
    """Theme part with a clrScheme: srgb values plus one sysClr slot."""
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{a}" name="Test Theme">
<a:themeElements>
<a:clrScheme name="Test">
<a:dk1><a:sysClr val="windowText" lastClr="1A1A1A"/></a:dk1>
<a:lt1><a:sysClr val="window" lastClr="FEFEFE"/></a:lt1>
<a:dk2><a:srgbClr val="44546A"/></a:dk2>
<a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>
<a:accent1><a:srgbClr val="4472C4"/></a:accent1>
<a:accent2><a:srgbClr val="ED7D31"/></a:accent2>
<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>
<a:accent4><a:srgbClr val="FFC000"/></a:accent4>
<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5>
<a:accent6><a:srgbClr val="70AD47"/></a:accent6>
<a:hlink><a:srgbClr val="0563C1"/></a:hlink>
<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
</a:clrScheme>
</a:themeElements>
</a:theme>"""


def ph_shape_xml(*, idx: str, ph_type: str, geometry: tuple[int, int, int, int] | None = None, shape_id: int = 2) -> str:
    """A placeholder p:sp (as found in layouts/masters), optionally with geometry."""
    xfrm = ""
    if geometry:
        x, y, cx, cy = geometry
        xfrm = f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
    return f"""<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="PH {idx}"/><p:cNvSpPr/>
<p:nvPr><p:ph type="{ph_type}" idx="{idx}"/></p:nvPr></p:nvSpPr>
<p:spPr>{xfrm}</p:spPr>
<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>
</p:sp>"""


def clr_map_xml(**mapping: str) -> str:
    attrs = " ".join(f'{name}="{value}"' for name, value in mapping.items())
    return f"<p:clrMap {attrs}/>"


def layout_xml(shapes_xml: str = "", *, clr_map: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
<p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/>{shapes_xml}</p:spTree></p:cSld>
{clr_map}
</p:sldLayout>"""


def master_xml(shapes_xml: str = "", *, clr_map: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
<p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/>{shapes_xml}</p:spTree></p:cSld>
{clr_map}
</p:sldMaster>"""
