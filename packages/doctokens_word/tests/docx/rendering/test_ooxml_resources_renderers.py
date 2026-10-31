"""Focused tests for OOXML helpers, resources, and renderer branches."""

from __future__ import annotations

import unittest
from io import BytesIO
from typing import Any, cast
from xml.etree import ElementTree as ET

from doctokens_core.containers.opc.relationships import RelationshipIndex
from doctokens_word.docx.model import ParseWarning, RelationshipRecord
from doctokens_word.docx.ooxml.numbering import NumberingInstance, NumberingLevel, NumberingMap, NumberingState
from doctokens_word.docx.parsing.modules.resources.assets import IMAGE_REL_TYPE, AssetExtractor
from doctokens_word.docx.rendering.dtx import _append_table


class NumberingAndAssetTests(unittest.TestCase):
    def test_numbering_state_formats_common_numbering_systems(self) -> None:
        formats = [
            ("ordinal", 21, "21st"),
            ("upperLetter", 27, "AA"),
            ("lowerLetter", 28, "bb"),
            ("chineseCounting", 21, "二十一"),
            ("japaneseDigitalTenThousand", 102, "一〇二"),
            ("unsupportedFormat", 3, "3"),
        ]
        levels = {
            index: NumberingLevel(
                numbering_level=index,
                start=start,
                number_format=number_format,
                suffix="nothing" if index % 2 == 0 else "space",
            )
            for index, (number_format, start, _expected) in enumerate(formats)
        }
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {"abstract": levels},
            {"7": NumberingInstance("7", "abstract")},
            warnings,
        )
        state = NumberingState(numbering, warnings)

        labels = []
        for index in range(len(formats)):
            label_obj = state.advance("7", index)
            assert label_obj is not None
            labels.append(label_obj["label"])

        self.assertEqual(labels, [expected for _fmt, _start, expected in formats])
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


class RendererBranchTests(unittest.TestCase):
    def test_table_renderers_cover_truncation_and_variants(self) -> None:

        rows = [
            {
                "rowIndex": index,
                "isHeader": index == 0,
                "cells": [
                    {
                        "rowIndex": index,
                        "colIndex": 0,
                        "rowSpan": 1,
                        "colSpan": 1,
                        "text": f"R{index}",
                        "blocks": [],
                    }
                ],
            }
            for index in range(31)
        ]
        table = {"type": "table", "tableId": "t-long", "rows": rows, "columnCount": 1}

        output = ET.Element("root")
        _append_table(output, cast(Any, table), "semantic", {})
        self.assertEqual(
            ET.tostring(output, encoding="unicode"),
            '<root><table id="t-long" truncated="true"><tr header="true"><th>R0</th></tr><tr><td>R1</td></tr></table></root>',
        )
        short = ET.Element("root")
        _append_table(short, cast(Any, {**table, "tableId": "t-short", "rows": rows[:2]}), "structural", {})
        self.assertEqual(
            ET.tostring(short, encoding="unicode"),
            '<root><table id="t-short"><tr header="true"><th>R0</th></tr><tr><td>R1</td></tr></table></root>',
        )


class FakePackage:
    def __init__(self, parts: dict[str, bytes]) -> None:
        self.parts = parts

    def exists(self, name: str) -> bool:
        return name in self.parts

    def open_entry(self, name: str) -> BytesIO:
        return BytesIO(self.parts[name])


if __name__ == "__main__":
    unittest.main()
