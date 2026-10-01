"""Theme parsing: clrScheme slots and Office default fallback."""

from __future__ import annotations

import unittest

from _pptx_fixtures import (
    content_types_xml,
    make_pptx,
    presentation_rels_xml,
    presentation_xml,
    root_rels_xml,
    theme_xml,
)
from pptx_llm_parser.core.models import ParseOptions
from pptx_llm_parser.parsing.runner import PptxParser
from pptx_llm_parser.plan import PptxFeature, PptxParsePlan

_THEME_REL = (
    '<Relationship Id="rId99" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
    'Target="theme/theme1.xml"/>'
)
_THEME_OVERRIDE = (
    '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
)


def _theme_deck(*, with_theme: bool = True) -> bytes:
    entries: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types_xml(1, extra_defaults=_THEME_OVERRIDE),
        "_rels/.rels": root_rels_xml(),
        "ppt/presentation.xml": presentation_xml(1),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(1, extra=_THEME_REL),
        "ppt/slides/slide1.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            "<p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/></p:spTree></p:cSld></p:sld>"
        ),
    }
    if with_theme:
        entries["ppt/theme/theme1.xml"] = theme_xml()
    return make_pptx(entries)


class ThemeParserTests(unittest.TestCase):
    def test_plain_plan_avoids_theme_and_layout_resolution(self) -> None:
        plan = PptxParsePlan.render("plain")
        self.assertFalse(plan.needs(PptxFeature.THEME_AND_LAYOUT))

    def test_missing_theme_part_falls_back_to_default_with_warning(self) -> None:
        parsed = PptxParser().parse(_theme_deck(with_theme=False), ParseOptions())
        self.assertTrue(any(w.code == "THEME_PART_MISSING" for w in parsed.warnings))


if __name__ == "__main__":
    unittest.main()
