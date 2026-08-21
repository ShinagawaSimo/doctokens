from __future__ import annotations

import unittest

from docx_llm_parser.core.models import ParseWarning, RelationshipRecord, StyleRecord
from docx_llm_parser.core.relationships import RelationshipIndex
from docx_llm_parser.ooxml.number_formats import NumberFormatRenderer
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

    def test_resolves_linked_character_format_for_paragraph_style(self) -> None:
        styles = StyleMap(
            {
                "char": StyleRecord(style_id="char", type="character", run_format={"smallCaps": True}),
                "para": StyleRecord(style_id="para", type="paragraph", link="char"),
            },
            [],
        )
        self.assertEqual(styles.resolve_run_format("para"), {"smallCaps": True})

    def test_exposes_numbering_style_num_ids_for_num_style_link(self) -> None:
        styles = StyleMap(
            {
                "list-style": StyleRecord(
                    style_id="list-style",
                    type="numbering",
                    numbering_num_id="12",
                ),
                "paragraph": StyleRecord(style_id="paragraph", type="paragraph"),
            },
            [],
        )
        self.assertEqual(dict(styles.numbering_style_num_ids()), {"list-style": "12"})

    def test_resolves_numbering_level_bound_to_paragraph_style(self) -> None:
        numbering = NumberingMap(
            {"abstract": {0: NumberingLevel(0, paragraph_style_id="CustomList")}},
            {
                "1": NumberingInstance(
                    "1",
                    "abstract",
                    level_overrides={1: NumberingLevel(1, paragraph_style_id="CustomList")},
                )
            },
            [],
        )
        self.assertEqual(numbering.level_for_style("1", "CustomList"), 1)


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
        self.assertEqual(NumberingState._chinese_counting(1010), "一千〇一十")
        self.assertEqual(NumberingState._chinese_counting(10000), "一万")
        self.assertEqual(NumberingState._chinese_counting(10050), "一万〇五十")

    def test_chinese_digital_keeps_each_digit_and_ideographic_zero(self) -> None:
        self.assertEqual(NumberingState._chinese_digital(12345), "一二三四五")
        self.assertEqual(NumberingState._chinese_digital(102), "一〇二")

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

    def test_none_numbering_level_has_no_visible_marker(self) -> None:
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {"abstract": {0: NumberingLevel(0, number_format="none", level_text="")}},
            {"1": NumberingInstance("1", "abstract")},
            warnings,
        )
        label = NumberingState(numbering, warnings).advance("1", 0)
        assert label is not None
        self.assertEqual(label["label"], "")
        self.assertEqual(label["text"], "")

    def test_level_restart_zero_preserves_deeper_counter(self) -> None:
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {
                "abstract": {
                    0: NumberingLevel(0, level_text="%1.", number_format="upperLetter"),
                    1: NumberingLevel(1, level_text="%1.%2.", restart_level=0),
                }
            },
            {"1": NumberingInstance("1", "abstract")},
            warnings,
        )
        state = NumberingState(numbering, warnings)
        state.advance("1", 0)
        first = state.advance("1", 1)
        state.advance("1", 0)
        second = state.advance("1", 1)
        assert first is not None and second is not None
        self.assertEqual(first["label"], "A.1.")
        self.assertEqual(second["label"], "B.2.")

    def test_legal_numbering_uses_decimal_for_referenced_levels(self) -> None:
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {
                "abstract": {
                    0: NumberingLevel(0, level_text="%1.", number_format="upperLetter"),
                    1: NumberingLevel(1, level_text="%1.%2.", number_format="lowerRoman", is_legal=True),
                }
            },
            {"1": NumberingInstance("1", "abstract")},
            warnings,
        )
        state = NumberingState(numbering, warnings)
        state.advance("1", 0)
        label = state.advance("1", 1)
        assert label is not None
        self.assertEqual(label["label"], "1.1.")
        self.assertTrue(label["legal"])

    def test_level_text_can_escape_a_literal_percent(self) -> None:
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {"abstract": {0: NumberingLevel(0, level_text="%% %1.")}},
            {"1": NumberingInstance("1", "abstract")},
            warnings,
        )
        label = NumberingState(numbering, warnings).advance("1", 0)
        assert label is not None
        self.assertEqual(label["label"], "% 1.")

    def test_formats_extended_standard_numbering_systems(self) -> None:
        formats = [
            ("chicago", 7, "**"),
            ("bahtText", 4, "4"),
            ("dollarText", 5, "5"),
            ("arabicAlpha", 1, "أ\u200c"),
            ("arabicAbjad", 1, "\u200cأ"),
            ("hebrew1", 15, "טו"),
            ("hebrew2", 23, "אא"),
            ("taiwaneseCounting", 21, "二十一"),
            ("taiwaneseDigital", 102, "一零二"),
            ("koreanDigital", 102, "일영이"),
            ("koreanCounting", 21, "이십일"),
        ]
        levels = {
            index: NumberingLevel(index, start=start, number_format=number_format, suffix="nothing")
            for index, (number_format, start, _expected) in enumerate(formats)
        }
        warnings: list[ParseWarning] = []
        state = NumberingState(
            NumberingMap({"abstract": levels}, {"1": NumberingInstance("1", "abstract")}, warnings),
            warnings,
        )

        labels = []
        for level in range(len(formats)):
            label = state.advance("1", level)
            assert label is not None
            labels.append(label["label"])

        self.assertEqual(labels, [expected for _format, _start, expected in formats])
        self.assertEqual(warnings, [])

    def test_enclosed_decimal_formats_follow_unicode_ranges(self) -> None:
        warnings: list[ParseWarning] = []
        renderer = NumberFormatRenderer(warnings)

        self.assertEqual(renderer.format(1, "decimalEnclosedCircle"), "①")
        self.assertEqual(renderer.format(20, "decimalEnclosedCircle"), "⑳")
        self.assertEqual(renderer.format(21, "decimalEnclosedCircle"), "㉑")
        self.assertEqual(renderer.format(35, "decimalEnclosedCircle"), "㉟")
        self.assertEqual(renderer.format(36, "decimalEnclosedCircle"), "㊱")
        self.assertEqual(renderer.format(50, "decimalEnclosedCircle"), "㊿")
        self.assertEqual(renderer.format(1, "decimalEnclosedFullstop"), "⒈")
        self.assertEqual(renderer.format(1, "decimalEnclosedParen"), "⑴")
        self.assertEqual(renderer.format(51, "decimalEnclosedCircle"), "51")
        self.assertEqual(warnings, [])

    def test_start_override_applies_to_a_full_level_override(self) -> None:
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {"abstract": {0: NumberingLevel(0, level_text="%1.")}},
            {
                "1": NumberingInstance(
                    "1",
                    "abstract",
                    level_overrides={0: NumberingLevel(0, level_text="(%1)", number_format="upperRoman")},
                    start_overrides={0: 5},
                )
            },
            warnings,
        )

        label = NumberingState(numbering, warnings).advance("1", 0)

        assert label is not None
        self.assertEqual(label["label"], "(V)")
        self.assertEqual(label["counter"], 5)

    def test_numbering_style_link_resolves_levels_from_linked_num(self) -> None:
        warnings: list[ParseWarning] = []
        numbering = NumberingMap(
            {
                "linked-abstract": {0: NumberingLevel(0, level_text="%1.", number_format="upperRoman")},
                "consumer-abstract": {},
            },
            {
                "linked-num": NumberingInstance("linked-num", "linked-abstract"),
                "consumer-num": NumberingInstance("consumer-num", "consumer-abstract"),
            },
            warnings,
            style_link_num_ids={"consumer-abstract": "linked-num"},
        )
        label = NumberingState(numbering, warnings).advance("consumer-num", 0)
        assert label is not None
        self.assertEqual(label["label"], "I.")


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
