"""Damaged picture bindings cannot be saved by ordinary PowerPoint image UI."""

import unittest
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from _pptx_images import image_deck
from doctokens_powerpoint import parse_pptx

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def damaged_picture(issue: str) -> bytes:
    # Only malformed-source coverage: delete a required blip/relationship/part.
    # The ordinary image input is shared OCR-transport infrastructure.
    with ZipFile(BytesIO(image_deck(alt="Readable"))) as source:
        entries = {part: source.read(part) for part in source.namelist()}
    if issue in {"blip", "rid"}:
        root = ET.fromstring(entries["ppt/slides/slide1.xml"])
        fill = root.find(".//" + _P + "blipFill")
        assert fill is not None
        blip = fill.find(_A + "blip")
        assert blip is not None
        if issue == "blip":
            fill.remove(blip)
        else:
            del blip.attrib[_R + "embed"]
        entries["ppt/slides/slide1.xml"] = ET.tostring(root)
    elif issue == "relationship":
        entries["ppt/slides/_rels/slide1.xml.rels"] = (
            b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
        )
    else:
        del entries["ppt/media/image1.png"]
    output = BytesIO()
    with ZipFile(output, "w") as target:
        for part, value in entries.items():
            target.writestr(part, value)
    return output.getvalue()


class UnreadablePictureTests(unittest.TestCase):
    def test_damaged_bindings_preserve_description_without_fake_resource_ids(self) -> None:
        for issue in ("blip", "rid", "relationship", "part"):
            source = damaged_picture(issue)
            for density in ("plain", "structural", "semantic"):
                with self.subTest(issue=issue, density=density):
                    result = parse_pptx(source, density=density)
                    if density == "plain":
                        self.assertEqual(result.text, "density=plain format=pptx\n=== Slide 1 ===\n[Image unavailable: Readable]")
                    else:
                        expected = (
                            f'<presentation density="{density}" format="pptx"><slide number="1">'
                            '<img alt="Readable" shape-id="s1"'
                            + (' name="Picture 3"' if density == "semantic" else "")
                            + '><unsupported type="image"/></img></slide></presentation>'
                        )
                        self.assertEqual(ET.canonicalize(result.text), ET.canonicalize(expected))
