"""pptx objects."""

from __future__ import annotations

from _pptx_namespaces import R_NS


def chart_shape_xml(*, rid: str = "rId2", name: str = "Chart 7", shape_id: int = 6) -> str:
    """Build a p:graphicFrame carrying an embedded chart reference."""
    return f"""<p:graphicFrame>
<p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
<p:xfrm/>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">
<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:r="{R_NS}" r:id="{rid}"/>
</a:graphicData></a:graphic>
</p:graphicFrame>"""


def chart_xml() -> str:
    """Minimal bar chart part with title and two series (2 categories each)."""
    c = "http://schemas.openxmlformats.org/drawingml/2006/chart"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"

    def series(name: str, values: str) -> str:
        v0, v1 = values.split(",")
        return (
            "<c:ser><c:tx><c:strRef><c:f>Sheet1!$B$1</c:f><c:strCache>"
            '<c:ptCount val="1"/><c:pt idx="0">'
            f"<c:v>{name}</c:v></c:pt></c:strCache></c:strRef></c:tx>"
            "<c:cat><c:strRef><c:f>Sheet1!$A$2:$A$3</c:f><c:strCache>"
            '<c:ptCount val="2"/>'
            '<c:pt idx="0"><c:v>East</c:v></c:pt>'
            '<c:pt idx="1"><c:v>West</c:v></c:pt>'
            "</c:strCache></c:strRef></c:cat>"
            "<c:val><c:numRef><c:f>Sheet1!$B$2:$B$3</c:f><c:numCache>"
            '<c:ptCount val="2"/>'
            f'<c:pt idx="0"><c:v>{v0}</c:v></c:pt>'
            f'<c:pt idx="1"><c:v>{v1}</c:v></c:pt>'
            "</c:numCache></c:numRef></c:val></c:ser>"
        )

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="{c}" xmlns:a="{a}">
<c:chart>
<c:title><c:tx><c:rich><a:bodyPr/><a:p><a:r><a:t>Sales</a:t></a:r></a:p></c:rich></c:tx></c:title>
<c:plotArea>
<c:barChart>
<c:barDir val="col"/>
{series("Q1", "10,20")}
{series("Q2", "15,25")}
</c:barChart>
</c:plotArea>
</c:chart>
</c:chartSpace>"""


def smartart_shape_xml(*, dm_rid: str = "rId2", lo_rid: str = "rId3", name: str = "Diagram 8", shape_id: int = 6) -> str:
    """Build a p:graphicFrame carrying a diagram (SmartArt) reference."""
    dgm = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
    return f"""<p:graphicFrame>
<p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
<p:xfrm/>
<a:graphic><a:graphicData uri="{dgm}">
<dgm:relIds xmlns:dgm="{dgm}" xmlns:r="{R_NS}" r:dm="{dm_rid}" r:lo="{lo_rid}" r:qs="" r:cs=""/>
</a:graphicData></a:graphic>
</p:graphicFrame>"""


def diagram_data_xml() -> str:
    """Minimal diagram data model: 3 nodes in a chain (1→2→3)."""
    dgm = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    mid1 = "{11111111-1111-1111-1111-111111111111}"
    mid2 = "{22222222-2222-2222-2222-222222222222}"
    mid3 = "{33333333-3333-3333-3333-333333333333}"

    def node(model_id: str, text: str) -> str:
        return (
            f'<dgm:pt modelId="{model_id}"><dgm:prSet/><dgm:t>'
            f"<a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></dgm:t></dgm:pt>"
        )

    def cxn(model_id: str, from_id: str, to_id: str) -> str:
        return f'<dgm:cxn modelId="{model_id}" fromModelId="{from_id}" toModelId="{to_id}"/>'

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<dgm:dataModel xmlns:dgm="{dgm}" xmlns:a="{a}">
<dgm:ptLst>
{node(mid1, "Start")}
{node(mid2, "Middle")}
{node(mid3, "End")}
</dgm:ptLst>
<dgm:cxnLst>
{cxn("c1", mid1, mid2)}
{cxn("c2", mid2, mid3)}
</dgm:cxnLst>
</dgm:dataModel>"""


def diagram_layout_xml() -> str:
    """Minimal diagram layout with a process category."""
    dgm = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<dgm:layoutDef xmlns:dgm="{dgm}">
<dgm:catLst><dgm:cat type="{dgm}/process"/></dgm:catLst>
</dgm:layoutDef>"""


def table_shape_xml(rows: list[list[str]], *, name: str = "Table 3", shape_id: int = 6) -> str:
    """Build a p:graphicFrame carrying an a:tbl with one paragraph per cell."""
    grid = '<a:gridCol w="100"/>' * len(rows[0]) if rows else ""
    trs = ""
    for row in rows:
        tcs = ""
        for text in row:
            tcs += f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>"
        trs += f'<a:tr h="0">{tcs}</a:tr>'
    return f"""<p:graphicFrame>
<p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
<p:xfrm/>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
<a:tbl><a:tblPr firstRow="1"/><a:tblGrid>{grid}</a:tblGrid>{trs}</a:tbl>
</a:graphicData></a:graphic>
</p:graphicFrame>"""
