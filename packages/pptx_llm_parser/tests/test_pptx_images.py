"""Picture shapes and lazy image asset indexing."""

from __future__ import annotations

import base64
import unittest

from _pptx_fixtures import (
    PNG_BYTES,
    content_types_xml,
    make_pptx,
    picture_shape_xml,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    slide_rels_xml,
    slide_xml_shapes,
)
from pptx_llm_parser import parse_pptx
from pptx_llm_parser.core.enums import Density
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parsing.runner import PptxParser


def _image_deck(*, alt: str | None = None, external: bool = False) -> bytes:
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


class ImageShapeTests(unittest.TestCase):
    def test_embedded_picture_shape_and_asset(self) -> None:
        parsed = PptxParser().parse(_image_deck(alt="Chart photo"), ParseOptions())
        shapes = parsed.slides[0]["shapes"]
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0]["type"], "picture")
        self.assertEqual(shapes[0]["assetId"], "img1")
        self.assertEqual(shapes[0]["alt"], "Chart photo")
        self.assertEqual(shapes[0]["name"], "Picture 3")
        self.assertEqual(len(parsed.assets), 1)
        asset = parsed.assets[0]
        self.assertEqual(asset["id"], "img1")
        self.assertEqual(asset["type"], "image")
        self.assertEqual(asset["source"], "embedded")
        self.assertEqual(asset["zipPath"], "ppt/media/image1.png")
        self.assertEqual(asset["contentType"], "image/png")

    def test_plain_image_placeholder_with_alt(self) -> None:
        text = parse_pptx(_image_deck(alt="Chart photo"), density=Density.PLAIN).text
        self.assertIn("[Image: Chart photo]", text)

    def test_plain_image_placeholder_without_alt(self) -> None:
        text = parse_pptx(_image_deck(), density=Density.PLAIN).text
        self.assertIn("[Image]", text)

    def test_external_image_records_href_only(self) -> None:
        parsed = PptxParser().parse(_image_deck(external=True), ParseOptions())
        shape = parsed.slides[0]["shapes"][0]
        self.assertEqual(shape["type"], "picture")
        self.assertEqual(shape["href"], "https://example.test/a.png")
        asset = parsed.assets[0]
        self.assertEqual(asset["source"], "external")
        self.assertEqual(asset["href"], "https://example.test/a.png")


if __name__ == "__main__":
    unittest.main()
