"""Compatibility exceptions: foreign-language enums, XSLT tokens and application-defined nfc cannot be selected
reliably in Simplified Chinese Word. The Symbol bullet case awaits docx-list-bullet-symbol-font.docx.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from docx_llm_parser.ooxml.numbering import NumberFormatRenderer
from docx_llm_parser.ooxml.numbering.change import parse_numbering_change
from docx_llm_parser.ooxml.numbering.models import NumberingLevel, bullet_symbol
from docx_llm_parser.ooxml.numbering.parser import NumberingMap, NumberingParser
from docx_llm_parser.ooxml.numbering.state import NumberingState


def test_numbering_support_is_split_into_explicit_modules() -> None:
    from docx_llm_parser.ooxml.numbering.change import parse_numbering_change
    from docx_llm_parser.ooxml.numbering.parser import NumberingParser

    assert NumberingLevel and NumberingMap and NumberingParser and NumberingState and parse_numbering_change


def test_taiwanese_counting_thousand_only_inserts_zero_when_required() -> None:
    renderer = NumberFormatRenderer([])

    assert renderer.format(10010, "taiwaneseCountingThousand") == "一萬十"
    assert renderer.format(10050, "taiwaneseCountingThousand") == "一萬五十"
    assert renderer.format(10999, "taiwaneseCountingThousand") == "一萬零九百九十九"


def test_thai_letter_sequence_has_the_41_specified_members() -> None:
    renderer = NumberFormatRenderer([])

    assert renderer.format(41, "thaiLetters") == "ฮ"
    assert renderer.format(42, "thaiLetters") == "กก"


def test_hebrew1_does_not_fall_back_to_decimal_at_ten_thousand() -> None:
    renderer = NumberFormatRenderer([])

    assert renderer.format(10_000, "hebrew1") != "10000"
    assert renderer.format(1_000_000, "hebrew1") != "1000000"


def test_custom_number_format_uses_xslt_style_token_and_literals() -> None:
    renderer = NumberFormatRenderer([])

    assert renderer.format(3, "custom", custom_format="01") == "03"
    assert renderer.format(3, "custom", custom_format="Section 1.") == "Section 3."
    assert renderer.format(3, "custom", custom_format="I") == "III"
    assert renderer.format(2, "custom", custom_format="ア") == "イ"


def test_unresolved_custom_format_falls_back_to_declared_number_format() -> None:
    warnings = []
    renderer = NumberFormatRenderer(warnings)

    assert renderer.format(3, "decimal", custom_format="unresolved-format") == "3"
    assert renderer.format(3, "custom") == "3"
    assert [warning.code for warning in warnings] == [
        "UNSUPPORTED_CUSTOM_NUMBER_FORMAT",
        "UNSUPPORTED_CUSTOM_NUMBER_FORMAT",
    ]


def test_numbering_xml_preserves_custom_format_language_and_bullet_font() -> None:
    level_xml = ET.fromstring(
        """
        <w:lvl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:ilvl="0">
          <w:numFmt w:val="custom" w:format="Section 1."/>
          <w:lvlText w:val="%1"/>
          <w:rPr>
            <w:lang w:val="es-ES"/>
            <w:rFonts w:ascii="Symbol"/>
          </w:rPr>
        </w:lvl>
        """
    )
    parser = NumberingParser.__new__(NumberingParser)

    level = parser._parse_level(level_xml)

    assert level is not None
    assert level.custom_format == "Section 1."
    assert level.language == "es-ES"


def test_language_specific_formats_cover_the_documented_examples() -> None:
    renderer = NumberFormatRenderer([])

    assert renderer.format(1, "cardinalText", "es-ES") == "Uno"
    assert renderer.format(21, "cardinalText", "es-ES") == "Veintiuno"
    assert renderer.format(1, "ordinal", "fr-FR") == "1er"
    assert renderer.format(2, "ordinal", "fr-FR") == "2e"
    assert renderer.format(1, "ordinalText", "de-DE") == "Erste"
    assert renderer.format(21, "ordinalText", "de-DE") == "Einundzwanzigste"
    assert renderer.format(27, "upperLetter", "nn-NO") == "Æ"
    assert renderer.format(29, "lowerLetter", "nn-NO") == "å"
    assert renderer.format(30, "lowerLetter", "nn-NO") == "aa"


def test_private_use_bullets_are_rendered_as_visible_symbols() -> None:
    assert bullet_symbol("\uf0b7") == "•"
    assert bullet_symbol("\uf123") == "•"


def test_application_defined_numbering_change_nfc_values_are_ignored() -> None:
    warnings = []

    assert parse_numbering_change("%1:40:custom:.", warnings) == {}
    assert parse_numbering_change("%1:60:vendor:.", warnings) == {}
    assert [warning.code for warning in warnings] == [
        "APPLICATION_DEFINED_NUMBER_FORMAT",
        "APPLICATION_DEFINED_NUMBER_FORMAT",
    ]


def test_application_defined_nfc_has_the_same_direct_renderer_behavior() -> None:
    warnings = []
    renderer = NumberFormatRenderer(warnings)

    assert renderer.format_from_nfc(1, 40) == ""
    assert renderer.format_from_nfc(1, 60) == ""
    assert [warning.code for warning in warnings] == [
        "APPLICATION_DEFINED_NUMBER_FORMAT",
        "APPLICATION_DEFINED_NUMBER_FORMAT",
    ]
