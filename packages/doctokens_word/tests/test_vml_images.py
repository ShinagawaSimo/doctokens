"""VML image degradation for malformed references and unknown producer branches.

Synthetic packages here intentionally contain dangling/missing image references
or unsupported extension branches, which desktop Office cannot reliably save.
Ordinary binding and both XML densities are also verified on the native tmp DOCX;
atomic native image fixtures remain in the existing real-file checklist.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from doctokens_word import parse_docx
from doctokens_word.core.constants import NS

from packages.doctokens_word.tests.test_body_structure import _make_docx

DECLARATIONS = f'xmlns:v="{NS["v"]}" xmlns:o="{NS["o"]}"'
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
IMAGE_TYPE = NS["r"] + "/image"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
PNG = Path(__file__).resolve().parents[3] / "test_support/fixture-assets/ff0000.png"


def _image_relationships(identifier: str, target: str) -> str:
    return (
        f'<Relationships xmlns="{REL_NS}"><Relationship Id="{identifier}" Type="{IMAGE_TYPE}" Target="{target}"/></Relationships>'
    )


def _abnormal_docx(body: str, entries: dict[str, str], *, with_image: bool = True) -> bytes:
    entries = {"word/styles.xml": f'<w:styles xmlns:w="{NS["w"]}"/>', **entries}
    buffer = BytesIO(_make_docx(body, entries))
    if with_image:
        with ZipFile(buffer, "a") as archive:
            archive.writestr("word/media/valid.png", PNG.read_bytes())
    return buffer.getvalue()


def _expected(density: str, body: str, *, assets: bool = True, supplemental: str = "") -> str:
    inventory = '<assets><img id="img1" /></assets>' if assets else ""
    return (
        f'<document density="{density}" format="docx" pagination="last-rendered-hints" revision-view="final">'
        f'<body><page number="1" /><p>{body}</p></body>{inventory}{supplemental}</document>'
    )


@pytest.mark.parametrize("density", ["structural", "semantic"])
def test_dangling_images_do_not_drop_valid_siblings_or_mix_shape_descriptions(density: str) -> None:
    body = f"""<w:p><w:r><w:pict {DECLARATIONS}><v:group>
      <v:shape id="name1" alt="A &amp; B"><v:imagedata r:id="valid"/></v:shape>
      <v:shape id="broken" alt="Missing"><v:imagedata r:id="dangling"/></v:shape>
      <v:shape id="box" alt="Caption"><v:textbox><w:txbxContent>
        <w:p><w:r><w:t>Note</w:t></w:r></w:p></w:txbxContent></v:textbox></v:shape>
      <v:rect id="name2" title="Title"><v:imagedata r:id="valid"/></v:rect>
      <v:shape id="name3"><v:imagedata r:id="valid" o:title="Image title"/></v:shape>
      <v:shape id="name4"><v:imagedata r:id="valid"/></v:shape>
      <v:shape id="empty"><v:imagedata/></v:shape>
    </v:group></w:pict></w:r></w:p>"""
    data = _abnormal_docx(
        body,
        {"word/_rels/document.xml.rels": _image_relationships("valid", "media/valid.png")},
    )
    result = parse_docx(data, density=density)
    visible = (
        '<img alt="A &amp; B" id="img1" /><img alt="Missing" /><textbox alt="Caption"><p>Note</p></textbox>'
        '<img alt="Title" id="img1" /><img alt="Image title" id="img1" /><img alt="name4" id="img1" /><img alt="empty" />'
        if density == "semantic"
        else '<img id="img1" /><img /><textbox><p>Note</p></textbox><img id="img1" /><img id="img1" /><img id="img1" /><img />'
    )
    assert result.text == _expected(density, visible)
    assert result.report.warnings == ()


@pytest.mark.parametrize("density", ["structural", "semantic"])
def test_missing_target_does_not_bind_same_relationship_id_from_another_part(density: str) -> None:
    # The body target was deleted; the header independently uses the same rId.
    body = f'<w:p><w:r><w:pict {DECLARATIONS}><v:shape alt="Deleted"><v:imagedata r:id="rId1"/></v:shape></w:pict></w:r></w:p>'
    header = (
        f'<w:hdr xmlns:w="{NS["w"]}" xmlns:r="{NS["r"]}"><w:p><w:r><w:pict {DECLARATIONS}>'
        '<v:shape alt="Header"><v:imagedata r:id="rId1"/></v:shape></w:pict></w:r></w:p></w:hdr>'
    )
    entries = {
        "word/_rels/document.xml.rels": _image_relationships("rId1", "media/deleted.png"),
        "word/header1.xml": header,
        "word/_rels/header1.xml.rels": _image_relationships("rId1", "media/valid.png"),
    }
    result = parse_docx(_abnormal_docx(body, entries), density=density)
    supplemental = (
        '<supplemental><headers><header id="header1" locator="headers.header1">'
        '<img alt="Header" id="img1" /></header></headers></supplemental>'
        if density == "semantic"
        else ""
    )
    assert result.text == _expected(
        density, '<img alt="Deleted" />' if density == "semantic" else "<img />", supplemental=supplemental
    )
    assert [(w.code, w.locator) for w in result.report.warnings] == [("IMAGE_TARGET_MISSING", "word/document.xml")]


@pytest.mark.parametrize("density", ["structural", "semantic"])
def test_unknown_producer_choice_can_fall_through_to_bound_vml_choice(density: str) -> None:
    body = f"""<w:p><w:r><mc:AlternateContent xmlns:mc="{MC}" {DECLARATIONS} xmlns:future="urn:future">
      <mc:Choice Requires="future"><future:image/></mc:Choice>
      <mc:Choice Requires="v"><w:pict><v:shape alt="VML"><v:imagedata r:id="valid"/></v:shape></w:pict></mc:Choice>
      <mc:Fallback><w:t>Unused</w:t></mc:Fallback>
    </mc:AlternateContent></w:r></w:p>"""
    entries = {"word/_rels/document.xml.rels": _image_relationships("valid", "media/valid.png")}
    result = parse_docx(_abnormal_docx(body, entries), density=density)
    assert result.text == _expected(density, '<img alt="VML" id="img1" />' if density == "semantic" else '<img id="img1" />')
    assert result.report.warnings == ()
    record = result.report.manifest["alternateContent"][0]
    assert (record["branch"], record["choiceIndex"]) == ("Choice", 2)


def test_dangling_vml_choice_uses_fallback_and_preserves_target_warning() -> None:
    body = f"""<w:p><w:r><mc:AlternateContent xmlns:mc="{MC}" {DECLARATIONS}>
      <mc:Choice Requires="v"><w:pict><v:shape><v:imagedata r:id="deleted"/></v:shape></w:pict></mc:Choice>
      <mc:Fallback><w:t>Visible fallback</w:t></mc:Fallback>
    </mc:AlternateContent></w:r></w:p>"""
    entries = {"word/_rels/document.xml.rels": _image_relationships("deleted", "media/deleted.png")}
    result = parse_docx(_abnormal_docx(body, entries, with_image=False))
    assert result.text == _expected("semantic", "Visible fallback", assets=False)
    assert [w.code for w in result.report.warnings] == ["IMAGE_TARGET_MISSING"]
    assert result.report.manifest["alternateContent"][0]["branch"] == "Fallback"
