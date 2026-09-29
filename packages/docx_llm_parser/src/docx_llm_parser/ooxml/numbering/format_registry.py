"""Format registry."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from .format_codes import _AIUEO_FULL_WIDTH, _AIUEO_HALF_WIDTH, _ARABIC_ABJAD, _ARABIC_ALPHA, _IROHA_FULL_WIDTH, _IROHA_HALF_WIDTH
from .format_east_asian import EastAsianNumberRenderer
from .format_sequences import (
    _arabic_sequence,
    _bounded_sequence,
    _chicago,
    _chinese_counting,
    _custom,
    _cycled_sequence,
    _decimal_ordinal,
    _decimal_zero,
    _enclosed_decimal,
    _hebrew_alphabet,
    _hebrew_numeral,
    _hexadecimal,
    _ideograph_enclosed_circle,
    _number_in_dash,
    _roman,
    _sexagenary_cycle,
    _translate_digits,
    _word_cycled_sequence,
    _word_letter_sequence,
    _word_repeated_sequence,
)
from .format_words import _english_cardinal, _english_ordinal, _hindi_counting, _thai_counting, _vietnamese_counting


def _build_formatters(east_asian: EastAsianNumberRenderer) -> dict[str, Callable[[int], str]]:
    """Register formats in the order used by 17.18.59."""
    return {
        "aiueo": partial(_word_cycled_sequence, sequence=_AIUEO_HALF_WIDTH),
        "aiueoFullWidth": partial(_word_cycled_sequence, sequence=_AIUEO_FULL_WIDTH),
        "arabicAbjad": partial(_arabic_sequence, sequence=_ARABIC_ABJAD, prefix="\u200c"),
        "arabicAlpha": partial(_arabic_sequence, sequence=_ARABIC_ALPHA, suffix="\u200c"),
        "bahtText": str,
        "bullet": str,
        "cardinalText": _english_cardinal,
        "chicago": _chicago,
        "chineseCounting": _chinese_counting,
        "chineseCountingThousand": east_asian._chinese_counting_thousand,
        "chineseLegalSimplified": east_asian._chinese_legal_simplified,
        "chosung": partial(_word_cycled_sequence, sequence="ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"),
        "custom": _custom,
        "decimal": str,
        "decimalEnclosedCircle": partial(_enclosed_decimal, start=0x2460, last=20),
        "decimalEnclosedCircleChinese": partial(_enclosed_decimal, start=0x2460, last=10),
        "decimalEnclosedFullstop": partial(_enclosed_decimal, start=0x2488, last=20),
        "decimalEnclosedParen": partial(_enclosed_decimal, start=0x2474, last=20),
        "decimalFullWidth": partial(_translate_digits, digits="０１２３４５６７８９"),
        "decimalFullWidth2": partial(_translate_digits, digits="０１２３４５６７８９"),
        "decimalHalfWidth": str,
        "decimalZero": _decimal_zero,
        "dollarText": str,
        "ganada": partial(_word_cycled_sequence, sequence="가나다라마바사아자차카타파하"),
        "hebrew1": _hebrew_numeral,
        "hebrew2": _hebrew_alphabet,
        "hex": _hexadecimal,
        "hindiConsonants": partial(
            _word_repeated_sequence,
            sequence=(*tuple(chr(codepoint) for codepoint in range(0x0905, 0x0915)), "अं", "अः"),
        ),
        "hindiCounting": _hindi_counting,
        "hindiNumbers": partial(_translate_digits, digits="०१२३४५६७८९"),
        "hindiVowels": partial(
            _word_repeated_sequence,
            sequence="".join(chr(codepoint) for codepoint in range(0x0915, 0x093A)),
        ),
        "ideographDigital": partial(_translate_digits, digits="〇一二三四五六七八九"),
        "ideographEnclosedCircle": _ideograph_enclosed_circle,
        "ideographLegalTraditional": east_asian._ideograph_legal_traditional,
        "ideographTraditional": partial(_bounded_sequence, sequence="甲乙丙丁戊己庚辛壬癸"),
        "ideographZodiac": partial(_bounded_sequence, sequence="子丑寅卯辰巳午未申酉戌亥"),
        "ideographZodiacTraditional": _sexagenary_cycle,
        "iroha": partial(_cycled_sequence, sequence=_IROHA_HALF_WIDTH),
        "irohaFullWidth": partial(_cycled_sequence, sequence=_IROHA_FULL_WIDTH),
        "japaneseCounting": east_asian._japanese_counting,
        "japaneseDigitalTenThousand": partial(_translate_digits, digits="〇一二三四五六七八九"),
        "japaneseLegal": east_asian._japanese_legal,
        "koreanCounting": east_asian._korean_counting,
        "koreanDigital": partial(_translate_digits, digits="영일이삼사오육칠팔구"),
        "koreanDigital2": partial(_translate_digits, digits="零一二三四五六七八九"),
        "koreanLegal": east_asian._korean_legal,
        "lowerLetter": partial(_word_letter_sequence, sequence="abcdefghijklmnopqrstuvwxyz"),
        "lowerRoman": lambda value: _roman(value).lower(),
        "none": lambda _value: "",
        "numberInDash": _number_in_dash,
        "ordinal": _decimal_ordinal,
        "ordinalText": _english_ordinal,
        "russianLower": partial(
            _word_repeated_sequence,
            sequence="".join(chr(codepoint) for codepoint in range(0x0430, 0x0439))
            + "".join(chr(codepoint) for codepoint in range(0x043A, 0x0440))
            + "".join(chr(codepoint) for codepoint in range(0x0440, 0x044A))
            + "ыэюя",
        ),
        "russianUpper": partial(
            _word_repeated_sequence,
            sequence="".join(chr(codepoint) for codepoint in range(0x0410, 0x0419))
            + "".join(chr(codepoint) for codepoint in range(0x041A, 0x0420))
            + "".join(chr(codepoint) for codepoint in range(0x0420, 0x042A))
            + "ЫЭЮЯ",
        ),
        "taiwaneseCounting": east_asian._taiwanese_counting,
        "taiwaneseCountingThousand": east_asian._taiwanese_counting_thousand,
        "taiwaneseDigital": partial(_translate_digits, digits="○一二三四五六七八九"),
        "thaiCounting": _thai_counting,
        "thaiLetters": partial(
            _word_repeated_sequence,
            sequence="กขค"
            + "".join(chr(codepoint) for codepoint in range(0x0E07, 0x0E24))
            + "ล"
            + "".join(chr(codepoint) for codepoint in range(0x0E27, 0x0E2F)),
        ),
        "thaiNumbers": partial(_translate_digits, digits="๐๑๒๓๔๕๖๗๘๙"),
        "upperLetter": partial(_word_letter_sequence, sequence="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        "upperRoman": _roman,
        "vietnameseCounting": _vietnamese_counting,
    }
