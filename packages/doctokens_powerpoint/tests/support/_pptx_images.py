"""Image-package input for OCR transport and session-lifecycle tests."""

from __future__ import annotations

import base64

from _pptx_namespaces import PNG_BYTES
from _pptx_package import (
    content_types_xml,
    make_pptx,
    picture_shape_xml,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
)


def image_deck(*, alt: str | None = None, external: bool = False) -> bytes:
    if external:
        rel = (
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="https://example.test/a.png" TargetMode="External"/>'
        )
    else:
        rel = (
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="../media/image1.png"/>'
        )
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1, extra_defaults='<Default Extension="png" ContentType="image/png"/>'),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1),
        "ppt/slides/slide1.xml": slide_xml_shapes(picture_shape_xml(alt=alt, external=external)),
        "ppt/slides/_rels/slide1.xml.rels": slide_rels_xml(rel),
    }
    if not external:
        entries["ppt/media/image1.png"] = base64.b64decode(PNG_BYTES)
    return make_pptx(entries)
