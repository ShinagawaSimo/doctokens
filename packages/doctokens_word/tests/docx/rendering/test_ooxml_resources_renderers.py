"""Focused tests for OOXML helpers, resources, and renderer branches."""

from __future__ import annotations

import unittest
from io import BytesIO
from typing import Any, cast

from doctokens_core.containers.opc.relationships import RelationshipIndex
from doctokens_word.docx.model import ParseWarning, RelationshipRecord
from doctokens_word.docx.ooxml.numbering import NumberingInstance, NumberingLevel, NumberingMap, NumberingState
from doctokens_word.docx.parsing.modules.resources.assets import IMAGE_REL_TYPE, AssetExtractor


class NumberingAndAssetTests(unittest.TestCase):
    def test_invalid_numbering_format_and_unresolved_instance(self) -> None:
        # These producer errors cannot be saved through normal Office numbering UI.
        levels = {0: NumberingLevel(numbering_level=0, start=3, number_format="unsupportedFormat", suffix="nothing")}
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {"abstract": levels},
            {"7": NumberingInstance("7", "abstract")},
            warnings,
        )
        state = NumberingState(numbering, warnings)

        label = state.advance("7", 0)
        assert label is not None
        self.assertEqual(label["label"], "3")
        self.assertEqual(warnings[0].code, "UNSUPPORTED_NUMBER_FORMAT")
        self.assertIsNone(state.advance("missing", 0, part="word/document.xml", block_id="b1"))
        self.assertEqual(warnings[-1].code, "NUMBERING_LEVEL_MISSING")

    def test_missing_image_target_warns(self) -> None:
        # A dangling relationship is not a normally saved Office document.
        warnings: list[ParseWarning] = []
        relationships = RelationshipIndex.from_records(
            [
                RelationshipRecord(
                    "word/document.xml",
                    "rMissing",
                    IMAGE_REL_TYPE,
                    "media/missing.png",
                    None,
                    "word/media/missing.png",
                ),
            ]
        )
        AssetExtractor(
            cast(Any, FakePackage({})),
            relationships,
            {"defaults": {}, "overrides": {}},
            warnings,
        ).extract()
        self.assertEqual([warning.code for warning in warnings], ["IMAGE_TARGET_MISSING"])


class FakePackage:
    def __init__(self, parts: dict[str, bytes]) -> None:
        self.parts = parts

    def exists(self, name: str) -> bool:
        return name in self.parts

    def open_entry(self, name: str) -> BytesIO:
        return BytesIO(self.parts[name])


if __name__ == "__main__":
    unittest.main()
