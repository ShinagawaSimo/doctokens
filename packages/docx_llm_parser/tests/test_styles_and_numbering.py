from __future__ import annotations

import unittest

from docx_llm_parser.core.models import ParseWarning, RelationshipRecord, StyleRecord
from docx_llm_parser.core.relationships import RelationshipIndex
from docx_llm_parser.ooxml.numbering import (
    NumberingInstance,
    NumberingLevel,
    NumberingMap,
    NumberingState,
)
from docx_llm_parser.ooxml.styles import StyleMap


class StyleMapTests(unittest.TestCase):
    def test_resolves_inherited_heading_numbering_and_run_format(self) -> None:
        warnings: list[ParseWarning] = []
        styles = StyleMap(
            {
                "base": StyleRecord(
                    style_id="base",
                    outline_level=1,
                    numbering_num_id="7",
                    numbering_level=2,
                    run_format={"bold": True, "color": "#123456"},
                ),
                "child": StyleRecord(
                    style_id="child",
                    based_on="base",
                    run_format={"bold": False, "italic": True},
                ),
            },
            warnings,
        )

        self.assertEqual(styles.resolve_heading_level("child"), 2)
        self.assertEqual(styles.resolve_numbering("child"), ("7", 2))
        self.assertEqual(
            styles.resolve_run_format("child"),
            {"color": "#123456", "italic": True},
        )
        self.assertEqual(warnings, [])


class NumberingStateTests(unittest.TestCase):
    def test_advances_and_resets_deeper_numbering_levels(self) -> None:
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {
                "abstract": {
                    0: NumberingLevel(0, level_text="%1."),
                    1: NumberingLevel(1, level_text="%1.%2."),
                }
            },
            {"9": NumberingInstance("9", "abstract")},
            warnings,
        )
        state = NumberingState(numbering, warnings)

        label = state.advance("9", 0)
        assert label is not None
        self.assertEqual(label["text"], "1.\t")
        label = state.advance("9", 1)
        assert label is not None
        self.assertEqual(label["text"], "1.1.\t")
        label = state.advance("9", 0)
        assert label is not None
        self.assertEqual(label["text"], "2.\t")
        label = state.advance("9", 1)
        assert label is not None
        self.assertEqual(label["text"], "2.1.\t")
        self.assertEqual(warnings, [])

    def test_chinese_counting_large_values(self) -> None:
        self.assertEqual(NumberingState._chinese_counting(1010), "一千零一十")
        self.assertEqual(NumberingState._chinese_counting(10000), "一万")
        self.assertEqual(NumberingState._chinese_counting(10050), "一万零五十")

    def test_numbering_value_beyond_chinese_range_falls_back(self) -> None:
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {"abstract": {0: NumberingLevel(0, level_text="%1.", number_format="chineseCounting", start=100_000_000)}},
            {"9": NumberingInstance("9", "abstract")},
            warnings,
        )
        state = NumberingState(numbering, warnings)
        label = state.advance("9", 0)
        assert label is not None
        self.assertEqual(label["text"], "100000000.\t")
        self.assertEqual([warning.code for warning in warnings], ["NUMBERING_VALUE_OUT_OF_RANGE"])


class ReadOnlyIndexContractTests(unittest.TestCase):
    def test_relationship_style_and_numbering_indexes_are_read_only(self) -> None:
        relationship = RelationshipRecord(
            source_part="word/document.xml",
            id="r1",
            type="image",
            target="media/image.png",
        )
        relationships = RelationshipIndex.from_records([relationship])
        styles = StyleMap({"base": StyleRecord(style_id="base")}, [])
        numbering = NumberingMap(
            {"abstract": {0: NumberingLevel(0)}},
            {"1": NumberingInstance("1", "abstract", start_overrides={0: 2})},
            [],
        )

        with self.assertRaises(TypeError):
            relationships._by_source_id[("word/document.xml", "r2")] = relationship  # type: ignore[index]
        with self.assertRaises(TypeError):
            styles.records["other"] = StyleRecord(style_id="other")  # type: ignore[index]
        with self.assertRaises(TypeError):
            numbering.abstract_levels["other"] = {}  # type: ignore[index]
        with self.assertRaises(TypeError):
            numbering.abstract_levels["abstract"][1] = NumberingLevel(1)  # type: ignore[index]
        with self.assertRaises(TypeError):
            numbering.instances["1"].start_overrides[1] = 3  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
