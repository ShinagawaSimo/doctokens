"""Render the visible value of Word ``w:numFmt`` numbering formats.

The format names and their basic algorithms come from ISO/IEC 29500
17.18.59. Microsoft Word's documented deviations are applied here rather
than in the numbering state machine; this keeps counter advancement and
visible number conversion separate.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from types import MappingProxyType
from typing import ClassVar

from ooxml_llm_core.text_numbering import roman_number

from ...core.models import ParseWarning, append_warning
from .language import cardinal_text, latin_alphabet, ordinal, ordinal_text


class NumberFormatRenderer:
    """Format one numbering value according to Word's ``ST_NumberFormat``."""

    _MAX_WORD_VALUE = 217_483_647
    _APPLICATION_DEFINED_NFC_VALUES = frozenset({40})
    _WORD_LIMITED_FORMATS = frozenset(
        {
            "cardinalText",
            "chineseCountingThousand",
            "chineseLegalSimplified",
            "ideographLegalTraditional",
            "japaneseCounting",
            "koreanCounting",
            "koreanDigital2",
            "ordinalText",
            "taiwaneseCountingThousand",
        }
    )

    # The sequences below are the code-point sets in 17.18.59, in document
    # order. Some of them intentionally look unusual: they are numbering
    # sequences, not attempts to transliterate the user's paragraph text.
    _AIUEO_HALF_WIDTH = (
        "\uff71\uff72\uff73\uff74\uff75\uff76\uff77\uff78\uff79\uff7a"
        "\uff7b\uff7c\uff7d\uff7e\uff7f\uff80\uff81\uff82\uff83\uff84"
        "\uff85\uff86\uff87\uff88\uff89\uff8a\uff8b\uff8c\uff8d\uff8e"
        "\uff8f\uff90\uff91\uff92\uff93\uff94\uff95\uff96\uff97\uff98"
        "\uff99\uff9a\uff9b\uff9c\uff66\uff9d"
    )
    _AIUEO_FULL_WIDTH = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
    _ARABIC_ABJAD = "أبجدهوزحطيكلمنسعفصقرشتثخذضظغ"
    _ARABIC_ALPHA = "أبتثجحخدذرزسشصضطظعغفقكلمنهوي"
    _HEBREW_ALPHABET = "אבגדהוזחטיכלמנסעפצקרשת"
    _IROHA_HALF_WIDTH = (
        "\uff72\uff9b\uff8a\uff86\uff8e\uff8d\uff84\uff81\uff98\uff87"
        "\uff99\uff66\uff9c\uff76\uff96\uff80\uff9a\uff7f\uff82\uff88"
        "\uff85\uff97\uff91\uff73\u30f0\uff89\uff75\uff78\uff94\uff8f"
        "\uff79\uff8c\uff7a\uff74\uff83\uff71\uff7b\uff77\uff95\uff92"
        "\uff90\uff7c\u30f1\uff8b\uff93\uff7e\uff7d\uff9d"
    )
    _IROHA_FULL_WIDTH = "イロハニホヘトチリヌルヲワカヨタレソツネナラムウヰノオクヤマケフコエテアサキユメミシヱヒモセス"
    _NFC_FORMATS: ClassVar[dict[int, str]] = {
        0: "decimal",
        1: "upperRoman",
        2: "lowerRoman",
        3: "upperLetter",
        4: "lowerLetter",
        5: "ordinal",
        6: "cardinalText",
        7: "ordinalText",
        8: "hex",
        9: "chicago",
        10: "ideographDigital",
        11: "japaneseCounting",
        12: "aiueo",
        13: "iroha",
        14: "decimalFullWidth",
        15: "decimalHalfWidth",
        16: "japaneseLegal",
        17: "japaneseDigitalTenThousand",
        18: "decimalEnclosedCircle",
        19: "decimalFullWidth2",
        20: "aiueoFullWidth",
        21: "irohaFullWidth",
        22: "decimalZero",
        23: "bullet",
        24: "ganada",
        25: "chosung",
        26: "decimalEnclosedFullstop",
        27: "decimalEnclosedParen",
        28: "decimalEnclosedCircleChinese",
        29: "ideographEnclosedCircle",
        30: "ideographTraditional",
        31: "ideographZodiac",
        32: "ideographZodiacTraditional",
        33: "taiwaneseCounting",
        34: "ideographLegalTraditional",
        35: "taiwaneseCountingThousand",
        36: "taiwaneseDigital",
        37: "chineseCounting",
        38: "chineseLegalSimplified",
        39: "chineseCountingThousand",
        41: "koreanDigital",
        42: "koreanCounting",
        43: "koreanLegal",
        44: "koreanDigital2",
        45: "hebrew1",
        46: "arabicAlpha",
        47: "hebrew2",
        48: "arabicAbjad",
        49: "hindiVowels",
        50: "hindiConsonants",
        51: "hindiNumbers",
        52: "hindiCounting",
        53: "thaiLetters",
        54: "thaiNumbers",
        55: "thaiCounting",
        56: "vietnameseCounting",
        57: "numberInDash",
        58: "russianLower",
        59: "russianUpper",
    }

    def __init__(self, warnings: list[ParseWarning]) -> None:
        self._warnings = warnings
        self._warned_formats: set[str] = set()
        self._warned_custom_formats: set[str] = set()
        self._warned_nfc_values: set[int] = set()
        self._warned_ranges: set[tuple[str, int]] = set()
        self._formatters: Mapping[str, Callable[[int], str]] = MappingProxyType(self._build_formatters())

    def format(
        self,
        value: int,
        number_format: str,
        language: str | None = None,
        custom_format: str | None = None,
    ) -> str:
        """Convert ``value`` to the text Word displays for ``number_format``."""
        if value > self._MAX_WORD_VALUE:
            return ""
        if number_format in self._WORD_LIMITED_FORMATS and value > 999_999:
            return self._out_of_range(value, number_format, display="")
        if number_format == "japaneseDigitalTenThousand" and value > 9_999:
            return self._out_of_range(value, number_format, display="")
        if number_format == "hex" and value > 65_535:
            return self._out_of_range(value, number_format, display="")
        if number_format == "koreanLegal" and value > 9_999_999:
            return self._out_of_range(value, number_format, display="")

        if custom_format:
            custom_value = self._format_custom(value, custom_format, language)
            if custom_value is not None:
                return custom_value
            self._warn_custom_format(custom_format, fallback=number_format)
        if number_format == "custom":
            if not custom_format:
                self._warn_custom_format(None, fallback="decimal")
            return str(value)
        if number_format == "cardinalText":
            return cardinal_text(value, language, self._english_cardinal)
        if number_format == "ordinal":
            return ordinal(value, language, self._decimal_ordinal)
        if number_format == "ordinalText":
            return ordinal_text(value, language, self._english_ordinal)
        if number_format in {"upperLetter", "lowerLetter"}:
            alphabet = latin_alphabet(language, upper=number_format == "upperLetter")
            if alphabet is not None:
                return self._word_letter_sequence(value, alphabet)

        formatter = self._formatters.get(number_format)
        if formatter is not None:
            return formatter(value)
        if number_format not in self._warned_formats:
            self._warned_formats.add(number_format)
            append_warning(
                self._warnings,
                "UNSUPPORTED_NUMBER_FORMAT",
                f"Unsupported numbering format {number_format!r}; decimal fallback is used.",
                part="word/numbering.xml",
            )
        return str(value)

    def format_from_nfc(self, value: int, nfc: int) -> str:
        """Format a ``numberingChange/@original`` NFC value."""
        number_format = self._NFC_FORMATS.get(nfc)
        if number_format is not None:
            return self.format(value, number_format)
        if self.is_application_defined_nfc(nfc):
            self._warn_application_defined_nfc(nfc)
        else:
            self._warn_unknown_nfc(nfc)
        return ""

    @classmethod
    def is_application_defined_nfc(cls, nfc: int) -> bool:
        """Return whether MS-OI29500 permits an NFC value to be ignored."""
        return nfc in cls._APPLICATION_DEFINED_NFC_VALUES or nfc >= 60

    def _build_formatters(self) -> dict[str, Callable[[int], str]]:
        """Register formats in the order used by 17.18.59."""
        return {
            "aiueo": partial(self._word_cycled_sequence, sequence=self._AIUEO_HALF_WIDTH),
            "aiueoFullWidth": partial(self._word_cycled_sequence, sequence=self._AIUEO_FULL_WIDTH),
            "arabicAbjad": partial(self._arabic_sequence, sequence=self._ARABIC_ABJAD, prefix="\u200c"),
            "arabicAlpha": partial(self._arabic_sequence, sequence=self._ARABIC_ALPHA, suffix="\u200c"),
            "bahtText": str,
            "bullet": str,
            "cardinalText": self._english_cardinal,
            "chicago": self._chicago,
            "chineseCounting": self._chinese_counting,
            "chineseCountingThousand": self._chinese_counting_thousand,
            "chineseLegalSimplified": self._chinese_legal_simplified,
            "chosung": partial(self._word_cycled_sequence, sequence="ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"),
            "custom": self._custom,
            "decimal": str,
            "decimalEnclosedCircle": partial(self._enclosed_decimal, start=0x2460, last=20),
            "decimalEnclosedCircleChinese": partial(self._enclosed_decimal, start=0x2460, last=10),
            "decimalEnclosedFullstop": partial(self._enclosed_decimal, start=0x2488, last=20),
            "decimalEnclosedParen": partial(self._enclosed_decimal, start=0x2474, last=20),
            "decimalFullWidth": partial(self._translate_digits, digits="０１２３４５６７８９"),
            "decimalFullWidth2": partial(self._translate_digits, digits="０１２３４５６７８９"),
            "decimalHalfWidth": str,
            "decimalZero": self._decimal_zero,
            "dollarText": str,
            "ganada": partial(self._word_cycled_sequence, sequence="가나다라마바사아자차카타파하"),
            "hebrew1": self._hebrew_numeral,
            "hebrew2": self._hebrew_alphabet,
            "hex": self._hexadecimal,
            "hindiConsonants": partial(
                self._word_repeated_sequence,
                sequence=(*tuple(chr(codepoint) for codepoint in range(0x0905, 0x0915)), "अं", "अः"),
            ),
            "hindiCounting": self._hindi_counting,
            "hindiNumbers": partial(self._translate_digits, digits="०१२३४५६७८९"),
            "hindiVowels": partial(
                self._word_repeated_sequence,
                sequence="".join(chr(codepoint) for codepoint in range(0x0915, 0x093A)),
            ),
            "ideographDigital": partial(self._translate_digits, digits="〇一二三四五六七八九"),
            "ideographEnclosedCircle": self._ideograph_enclosed_circle,
            "ideographLegalTraditional": self._ideograph_legal_traditional,
            "ideographTraditional": partial(self._bounded_sequence, sequence="甲乙丙丁戊己庚辛壬癸"),
            "ideographZodiac": partial(self._bounded_sequence, sequence="子丑寅卯辰巳午未申酉戌亥"),
            "ideographZodiacTraditional": self._sexagenary_cycle,
            "iroha": partial(self._cycled_sequence, sequence=self._IROHA_HALF_WIDTH),
            "irohaFullWidth": partial(self._cycled_sequence, sequence=self._IROHA_FULL_WIDTH),
            "japaneseCounting": self._japanese_counting,
            "japaneseDigitalTenThousand": partial(self._translate_digits, digits="〇一二三四五六七八九"),
            "japaneseLegal": self._japanese_legal,
            "koreanCounting": self._korean_counting,
            "koreanDigital": partial(self._translate_digits, digits="영일이삼사오육칠팔구"),
            "koreanDigital2": partial(self._translate_digits, digits="零一二三四五六七八九"),
            "koreanLegal": self._korean_legal,
            "lowerLetter": partial(self._word_letter_sequence, sequence="abcdefghijklmnopqrstuvwxyz"),
            "lowerRoman": lambda value: self._roman(value).lower(),
            "none": lambda _value: "",
            "numberInDash": self._number_in_dash,
            "ordinal": self._decimal_ordinal,
            "ordinalText": self._english_ordinal,
            "russianLower": partial(
                self._word_repeated_sequence,
                sequence="".join(chr(codepoint) for codepoint in range(0x0430, 0x0439))
                + "".join(chr(codepoint) for codepoint in range(0x043A, 0x0440))
                + "".join(chr(codepoint) for codepoint in range(0x0440, 0x044A))
                + "ыэюя",
            ),
            "russianUpper": partial(
                self._word_repeated_sequence,
                sequence="".join(chr(codepoint) for codepoint in range(0x0410, 0x0419))
                + "".join(chr(codepoint) for codepoint in range(0x041A, 0x0420))
                + "".join(chr(codepoint) for codepoint in range(0x0420, 0x042A))
                + "ЫЭЮЯ",
            ),
            "taiwaneseCounting": self._taiwanese_counting,
            "taiwaneseCountingThousand": self._taiwanese_counting_thousand,
            "taiwaneseDigital": partial(self._translate_digits, digits="○一二三四五六七八九"),
            "thaiCounting": self._thai_counting,
            "thaiLetters": partial(
                self._word_repeated_sequence,
                sequence="กขค"
                + "".join(chr(codepoint) for codepoint in range(0x0E07, 0x0E24))
                + "ล"
                + "".join(chr(codepoint) for codepoint in range(0x0E27, 0x0E2F)),
            ),
            "thaiNumbers": partial(self._translate_digits, digits="๐๑๒๓๔๕๖๗๘๙"),
            "upperLetter": partial(self._word_letter_sequence, sequence="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            "upperRoman": self._roman,
            "vietnameseCounting": self._vietnamese_counting,
        }

    # Basic formats -----------------------------------------------------

    @staticmethod
    def _decimal_ordinal(value: int) -> str:
        suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
        return f"{value}{suffix}"

    @staticmethod
    def _decimal_zero(value: int) -> str:
        return f"{value:02d}"

    @staticmethod
    def _number_in_dash(value: int) -> str:
        return f"- {value} -"

    def _custom(self, value: int) -> str:
        return str(value)

    def _format_custom(self, value: int, pattern: str, language: str | None) -> str | None:
        """Render the XSLT format subset that Word numbering exposes."""
        if pattern == "ア":
            return self._word_cycled_sequence(value, self._AIUEO_FULL_WIDTH)
        if pattern == "ｱ":
            return self._word_cycled_sequence(value, self._AIUEO_HALF_WIDTH)
        if not pattern:
            return None
        token_match = next(
            (match for match in re.finditer(r"[A-Za-z0-9]+", pattern) if set(match.group(0)) <= {"0", "1", "A", "a", "I", "i"}),
            None,
        )
        if token_match is None:
            return None
        token = token_match.group(0)
        if set(token) <= {"0", "1"} and "1" in token:
            rendered = str(value).zfill(len(token))
        elif set(token) == {"A"}:
            rendered = self._word_letter_sequence(value, latin_alphabet(language, upper=True) or "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        elif set(token) == {"a"}:
            rendered = self._word_letter_sequence(value, latin_alphabet(language, upper=False) or "abcdefghijklmnopqrstuvwxyz")
        elif set(token) == {"I"}:
            rendered = self._roman(value)
        elif set(token) == {"i"}:
            rendered = self._roman(value).lower()
        else:
            return None
        return pattern[: token_match.start()] + rendered + pattern[token_match.end() :]

    def _warn_custom_format(self, pattern: str | None, *, fallback: str) -> None:
        key = f"{pattern!r}:{fallback}"
        if key in self._warned_custom_formats:
            return
        self._warned_custom_formats.add(key)
        description = "is missing" if pattern is None else f"{pattern!r} is not supported"
        append_warning(
            self._warnings,
            "UNSUPPORTED_CUSTOM_NUMBER_FORMAT",
            f"Custom numbering format {description}; {fallback} is used instead.",
            part="word/numbering.xml",
        )

    def _warn_application_defined_nfc(self, nfc: int) -> None:
        if nfc in self._warned_nfc_values:
            return
        self._warned_nfc_values.add(nfc)
        append_warning(
            self._warnings,
            "APPLICATION_DEFINED_NUMBER_FORMAT",
            f"Application-defined numberingChange NFC value {nfc} was ignored.",
            part="word/document.xml",
        )

    def _warn_unknown_nfc(self, nfc: int) -> None:
        if nfc in self._warned_nfc_values:
            return
        self._warned_nfc_values.add(nfc)
        append_warning(
            self._warnings,
            "INVALID_NUMBERING_CHANGE",
            f"Unknown numberingChange NFC value {nfc} was ignored.",
            part="word/document.xml",
        )

    @staticmethod
    def _hexadecimal(value: int) -> str:
        return f"{value:X}" if 0 <= value <= 65_535 else str(value)

    @staticmethod
    def _roman(value: int) -> str:
        return roman_number(value)

    @staticmethod
    def _translate_digits(value: int, digits: str) -> str:
        if value < 0:
            return str(value)
        return "".join(digits[int(character)] if character.isdigit() else character for character in str(value))

    @staticmethod
    def _chinese_digital(value: int) -> str:
        return NumberFormatRenderer._translate_digits(value, digits="〇一二三四五六七八九")

    # Repeating/cyclic alphabet formats --------------------------------

    @staticmethod
    def _word_repeated_sequence(value: int, sequence: Sequence[str]) -> str:
        if value <= 0 or not sequence:
            return str(value)
        quotient, remainder = divmod(value - 1, len(sequence))
        return sequence[remainder] * (quotient + 1)

    @staticmethod
    def _word_cycled_sequence(value: int, sequence: str) -> str:
        if value <= 0 or not sequence:
            return str(value)
        return sequence[(value - 1) % len(sequence)]

    @classmethod
    def _word_letter_sequence(cls, value: int, sequence: str) -> str:
        return cls._word_repeated_sequence(value, sequence) if value <= len(sequence) * 30 else str(value)

    @classmethod
    def _arabic_sequence(cls, value: int, sequence: str, prefix: str = "", suffix: str = "") -> str:
        return prefix + cls._word_repeated_sequence(value, sequence) + suffix

    @staticmethod
    def _cycled_sequence(value: int, sequence: str) -> str:
        if value <= 0 or not sequence:
            return str(value)
        return sequence[(value - 1) % len(sequence)]

    @staticmethod
    def _bounded_sequence(value: int, sequence: str) -> str:
        return sequence[value - 1] if 1 <= value <= len(sequence) else str(value)

    @staticmethod
    def _enclosed_decimal(value: int, start: int, last: int) -> str:
        return chr(start + value - 1) if 1 <= value <= last else str(value)

    @staticmethod
    def _ideograph_enclosed_circle(value: int) -> str:
        if 1 <= value <= 10:
            return f"({chr(0x3220 + value - 1)})"
        return str(value)

    # East Asian number formats ----------------------------------------

    @staticmethod
    def _chinese_counting(value: int) -> str:
        if value < 0:
            return str(value)
        digits = "○一二三四五六七八九"
        if value <= 10:
            return digits[value] if value < 10 else "十"
        if value < 100:
            tens, ones = divmod(value, 10)
            prefix = "十" if tens == 1 else digits[tens] + "十"
            return prefix + ("" if not ones else digits[ones])
        return NumberFormatRenderer._translate_digits(value, digits=digits)

    def _chinese_counting_thousand(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, "chineseCountingThousand", display="")
        if value < 10_000:
            return self._unit_counting(value, "〇一二三四五六七八九", "十百千", zero="〇")
        high, low = divmod(value, 10_000)
        result = (
            self._unit_counting(
                high,
                "〇一二三四五六七八九",
                "十百千",
                zero="〇",
                omit_one_ten=value < 100_000,
            )
            + "万"
        )
        if low:
            # Word renders the zero between the ten-thousands group and a
            # lower group below one thousand (for example, 一万〇五十).
            if low < 1_000:
                result += "〇"
            result += self._unit_counting(low, "〇一二三四五六七八九", "十百千", zero="〇")
        return result

    def _taiwanese_counting(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value < 100:
            return self._unit_counting(value, "○一二三四五六七八九", "十百千", zero="○")
        return self._translate_digits(value, digits="○一二三四五六七八九")

    def _taiwanese_counting_thousand(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, "taiwaneseCountingThousand", display="")
        if value < 10_000:
            return self._unit_counting(value, "零一二三四五六七八九", "十百千", zero="零")
        high, low = divmod(value, 10_000)
        result = (
            self._unit_counting(
                high,
                "零一二三四五六七八九",
                "十百千",
                zero="零",
                omit_one_ten=value < 100_000,
            )
            + "萬"
        )
        if low:
            if low < 1_000 and value % 10 != 0:
                result += "零"
            result += self._unit_counting(low, "零一二三四五六七八九", "十百千", zero="零")
        return result

    @staticmethod
    def _unit_counting(
        value: int,
        digits: str,
        units: str,
        *,
        zero: str,
        omit_one_ten: bool = True,
        omit_one_units: bool = False,
        insert_zero: bool = True,
    ) -> str:
        if value == 0:
            return digits[0]
        if value < 0:
            return str(value)

        parts: list[str] = []
        pending_zero = False
        remaining = value
        for divisor, unit in ((1000, units[2]), (100, units[1]), (10, units[0])):
            digit, remaining = divmod(remaining, divisor)
            if digit:
                if pending_zero and insert_zero:
                    parts.append(zero)
                pending_zero = False
                omit_one = (divisor == 10 and omit_one_ten) or omit_one_units
                if not (digit == 1 and not parts and omit_one):
                    parts.append(digits[digit])
                parts.append(unit)
            elif parts and remaining:
                pending_zero = True
        if remaining:
            if pending_zero and insert_zero:
                parts.append(zero)
            parts.append(digits[remaining])
        return "".join(parts)

    def _chinese_legal_simplified(self, value: int) -> str:
        return self._legal_counting(
            value,
            digits="零壹贰叁肆伍陆柒捌玖",
            units="拾佰仟",
            large_unit="萬",
            format_name="chineseLegalSimplified",
        )

    def _ideograph_legal_traditional(self, value: int) -> str:
        return self._legal_counting(
            value,
            digits="零壹貳叁肆伍陸柒捌玖",
            units="拾佰仟",
            large_unit="萬",
            format_name="ideographLegalTraditional",
        )

    def _legal_counting(
        self,
        value: int,
        *,
        digits: str,
        units: str,
        large_unit: str,
        format_name: str,
    ) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, format_name, display="")
        if value < 10_000:
            return self._unit_counting(value, digits, units, zero=digits[0], omit_one_ten=False)
        high, low = divmod(value, 10_000)
        result = self._unit_counting(high, digits, units, zero=digits[0], omit_one_ten=False) + large_unit
        if low:
            if low < 1_000:
                result += digits[0]
            result += self._unit_counting(low, digits, units, zero=digits[0], omit_one_ten=False)
        return result

    def _japanese_counting(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, "japaneseCounting", display="")
        if value < 10_000:
            return self._unit_counting(
                value,
                "〇一二三四五六七八九",
                "十百千",
                zero="〇",
                omit_one_units=True,
                insert_zero=False,
            )
        high, low = divmod(value, 10_000)
        result = (
            self._unit_counting(
                high,
                "〇一二三四五六七八九",
                "十百千",
                zero="〇",
                omit_one_units=True,
                insert_zero=False,
            )
            + "万"
        )
        return (
            result
            if not low
            else result
            + self._unit_counting(
                low,
                "〇一二三四五六七八九",
                "十百千",
                zero="〇",
                omit_one_units=True,
                insert_zero=False,
            )
        )

    def _japanese_legal(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value >= 100_000_000:
            high, low = divmod(value, 100_000_000)
            result = (
                self._unit_counting(
                    high,
                    "〇壱弐参四伍六七八九",
                    "拾百阡",
                    zero="〇",
                    omit_one_ten=False,
                )
                + "億"
            )
            if low:
                result += self._japanese_legal_under_100m(low)
            return result
        return self._japanese_legal_under_100m(value)

    def _japanese_legal_under_100m(self, value: int) -> str:
        if value < 10_000:
            return self._unit_counting(value, "〇壱弐参四伍六七八九", "拾百阡", zero="〇", omit_one_ten=False, insert_zero=False)
        high, low = divmod(value, 10_000)
        result = (
            self._unit_counting(
                high,
                "〇壱弐参四伍六七八九",
                "拾百阡",
                zero="〇",
                omit_one_ten=False,
            )
            + "萬"
        )
        if low:
            result += self._unit_counting(
                low,
                "〇壱弐参四伍六七八九",
                "拾百阡",
                zero="〇",
                omit_one_ten=False,
                insert_zero=False,
            )
        return result

    def _korean_counting(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 999_999:
            return self._out_of_range(value, "koreanCounting", display="")
        return self._korean_unit_counting(value)

    @staticmethod
    def _korean_unit_counting(value: int) -> str:
        if value == 0:
            return "영"
        digits = "영일이삼사오육칠팔구"
        units = "십백천"
        if value < 10_000:
            return NumberFormatRenderer._unit_counting(
                value,
                digits,
                units,
                zero="영",
                omit_one_units=True,
                insert_zero=False,
            )
        high, low = divmod(value, 10_000)
        high_text = (
            ""
            if high == 1
            else NumberFormatRenderer._unit_counting(
                high,
                digits,
                units,
                zero="영",
                omit_one_units=True,
                insert_zero=False,
            )
        )
        result = high_text + "만"
        return (
            result
            if not low
            else result
            + NumberFormatRenderer._unit_counting(
                low,
                digits,
                units,
                zero="영",
                omit_one_units=True,
                insert_zero=False,
            )
        )

    def _korean_legal(self, value: int) -> str:
        if value < 0:
            return str(value)
        if value > 9_999_999:
            return self._out_of_range(value, "koreanLegal", display="")
        if value < 100:
            small = {
                0: "영",
                1: "하나",
                2: "둘",
                3: "셋",
                4: "넷",
                5: "다섯",
                6: "여섯",
                7: "일곱",
                8: "여덟",
                9: "아홉",
                10: "열",
                20: "스물",
                30: "서른",
                40: "마흔",
                50: "쉰",
                60: "예순",
                70: "일흔",
                80: "여든",
                90: "아흔",
            }
            tens, ones = divmod(value, 10)
            if tens == 0 or ones == 0:
                return small[value]
            return small[tens * 10] + small[ones]
        return self._korean_unit_counting(value)

    def _sexagenary_cycle(self, value: int) -> str:
        if value <= 0:
            return str(value)
        stems = "甲乙丙丁戊己庚辛壬癸"
        branches = "子丑寅卯辰巳午未申酉戌亥"
        index = (value - 1) % 60
        return stems[index % 10] + branches[index % 12]

    # Hebrew and non-Asian text formats -------------------------------

    @staticmethod
    def _hebrew_numeral(value: int) -> str:
        if value <= 0:
            return str(value)
        thousands, remainder = divmod(value, 1000)
        parts = NumberFormatRenderer._hebrew_numeral(thousands) if thousands else ""
        hundreds, remainder = divmod(remainder, 100)
        if hundreds:
            parts += "קרשתךםןףץ"[hundreds - 1]
        if remainder in {15, 16}:
            return parts + ("טו" if remainder == 15 else "טז")
        tens, units = divmod(remainder, 10)
        if tens:
            parts += "יכלמנסעפצ"[tens - 1]
        if units:
            parts += "אבגדהוזחט"[units - 1]
        return parts

    @classmethod
    def _hebrew_alphabet(cls, value: int) -> str:
        if value <= 0:
            return str(value)
        quotient, remainder = divmod(value - 1, len(cls._HEBREW_ALPHABET))
        return "\u200f" + cls._HEBREW_ALPHABET[remainder] + "ת" * quotient

    @staticmethod
    def _chicago(value: int) -> str:
        if value <= 0 or value > 116:
            return "" if value > 116 else str(value)
        symbols = "*†‡§"
        quotient, remainder = divmod(value - 1, len(symbols))
        return symbols[remainder] * (quotient + 1)

    # Language examples ------------------------------------------------

    @staticmethod
    def _english_cardinal(value: int) -> str:
        if value < 0 or value > 999_999:
            return ""
        ones = (
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        )
        tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")

        def under_thousand(number: int) -> str:
            if number < 20:
                return ones[number]
            if number < 100:
                quotient, remainder = divmod(number, 10)
                return tens[quotient] if not remainder else f"{tens[quotient]}-{ones[remainder]}"
            quotient, remainder = divmod(number, 100)
            return f"{ones[quotient]} hundred" if not remainder else f"{ones[quotient]} hundred {under_thousand(remainder)}"

        if value < 1000:
            return under_thousand(value).title()
        quotient, remainder = divmod(value, 1000)
        result = f"{under_thousand(quotient)} thousand"
        return result.title() if not remainder else f"{result} {under_thousand(remainder)}".title()

    @classmethod
    def _english_ordinal(cls, value: int) -> str:
        if value < 0 or value > 999_999:
            return ""
        special = {
            "zero": "zeroth",
            "one": "first",
            "two": "second",
            "three": "third",
            "four": "fourth",
            "five": "fifth",
            "six": "sixth",
            "seven": "seventh",
            "eight": "eighth",
            "nine": "ninth",
            "ten": "tenth",
            "eleven": "eleventh",
            "twelve": "twelfth",
            "thirteen": "thirteenth",
            "fourteen": "fourteenth",
            "fifteen": "fifteenth",
            "sixteen": "sixteenth",
            "seventeen": "seventeenth",
            "eighteen": "eighteenth",
            "nineteen": "nineteenth",
            "twenty": "twentieth",
            "thirty": "thirtieth",
            "forty": "fortieth",
            "fifty": "fiftieth",
            "sixty": "sixtieth",
            "seventy": "seventieth",
            "eighty": "eightieth",
            "ninety": "ninetieth",
            "hundred": "hundredth",
            "thousand": "thousandth",
        }
        cardinal = cls._english_cardinal(value).lower()
        prefix, separator, tail = cardinal.rpartition("-")
        if separator:
            return f"{prefix}-{special.get(tail, tail + 'th')}"
        prefix, separator, tail = cardinal.rpartition(" ")
        ordinal_tail = special.get(tail, tail + "th")
        return (f"{prefix} {ordinal_tail}" if separator else ordinal_tail).title()

    @staticmethod
    def _hindi_counting(value: int) -> str:
        if value < 0:
            return str(value)
        if value > NumberFormatRenderer._MAX_WORD_VALUE:
            return ""

        words = (
            "शून्य",
            "एक",
            "दो",
            "तीन",
            "चार",
            "पाँच",
            "छह",
            "सात",
            "आठ",
            "नौ",
            "दस",
            "ग्यारह",
            "बारह",
            "तेरह",
            "चौदह",
            "पंद्रह",
            "सोलह",
            "सत्रह",
            "अठारह",
            "उन्नीस",
            "बीस",
            "इक्कीस",
            "बाईस",
            "तेईस",
            "चौबीस",
            "पच्चीस",
            "छब्बीस",
            "सत्ताईस",
            "अट्ठाईस",
            "उनतीस",
            "तीस",
            "इकतीस",
            "बत्तीस",
            "तैंतीस",
            "चौंतीस",
            "पैंतीस",
            "छत्तीस",
            "सैंतीस",
            "अड़तीस",
            "उनतालीस",
            "चालीस",
            "इकतालीस",
            "बयालीस",
            "तैंतालीस",
            "चवालीस",
            "पैंतालीस",
            "छियालीस",
            "सैंतालीस",
            "अड़तालीस",
            "उनचास",
            "पचास",
            "इक्यावन",
            "बावन",
            "तिरपन",
            "चौवन",
            "पचपन",
            "छप्पन",
            "सत्तावन",
            "अट्ठावन",
            "उनसठ",
            "साठ",
            "इकसठ",
            "बासठ",
            "तिरसठ",
            "चौंसठ",
            "पैंसठ",
            "छियासठ",
            "सड़सठ",
            "अड़सठ",
            "उनहत्तर",
            "सत्तर",
            "इकहत्तर",
            "बहत्तर",
            "तिहत्तर",
            "चौहत्तर",
            "पचहत्तर",
            "छिहत्तर",
            "सतहत्तर",
            "अठहत्तर",
            "उन्नासी",
            "अस्सी",
            "इक्यासी",
            "बयासी",
            "तिरासी",
            "चौरासी",
            "पचासी",
            "छियासी",
            "सतासी",
            "अट्ठासी",
            "नवासी",
            "नब्बे",
            "इक्यानबे",
            "बानबे",
            "तिरानबे",
            "चौरानबे",
            "पंचानबे",
            "छियानबे",
            "सत्तानबे",
            "अट्ठानबे",
            "निन्यानबे",
        )

        def under_hundred(number: int) -> str:
            return words[number]

        def under_thousand(number: int) -> str:
            hundreds, remainder = divmod(number, 100)
            parts: list[str] = []
            if hundreds:
                parts.extend((words[hundreds], "सौ"))
            if remainder:
                parts.append(under_hundred(remainder))
            return " ".join(parts)

        def under_lakh(number: int) -> str:
            thousands, remainder = divmod(number, 1000)
            parts: list[str] = []
            if thousands:
                parts.append(under_hundred(thousands) + " हज़ार")
            if remainder:
                parts.append(under_thousand(remainder))
            return " ".join(parts)

        if value < 100:
            return under_hundred(value)
        crores, remainder = divmod(value, 10_000_000)
        parts: list[str] = []
        if crores:
            parts.append(under_hundred(crores) + " करोड़")
        lakhs, remainder = divmod(remainder, 100_000)
        if lakhs:
            parts.append(under_hundred(lakhs) + " लाख")
        if remainder:
            parts.append(under_lakh(remainder))
        if value < 100_000:
            return under_lakh(value)
        return " ".join(parts)

    @staticmethod
    def _thai_counting(value: int) -> str:
        if value < 0:
            return str(value)
        digits = ("ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า")
        if value == 0:
            return digits[0]

        def under_million(number: int) -> str:
            if number >= 1_000_000:
                quotient, remainder = divmod(number, 1_000_000)
                return under_million(quotient) + "ล้าน" + (under_million(remainder) if remainder else "")
            parts: list[str] = []
            for divisor, unit in ((100_000, "แสน"), (10_000, "หมื่น"), (1_000, "พัน"), (100, "ร้อย")):
                quotient, number = divmod(number, divisor)
                if quotient:
                    parts.append(("หนึ่ง" if quotient == 1 else under_million(quotient)) + unit)
            quotient, number = divmod(number, 10)
            if quotient:
                parts.append("สิบ" if quotient == 1 else "ยี่สิบ" if quotient == 2 else digits[quotient] + "สิบ")
            if number:
                parts.append("เอ็ด" if parts and number == 1 else digits[number])
            return "".join(parts)

        return under_million(value)

    @staticmethod
    def _vietnamese_counting(value: int) -> str:
        if value < 0:
            return str(value)
        if value > NumberFormatRenderer._MAX_WORD_VALUE:
            return ""
        digits = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")

        def under_hundred(number: int) -> str:
            if number < 10:
                return digits[number]
            tens, ones = divmod(number, 10)
            prefix = "mười" if tens == 1 else digits[tens] + " mươi"
            if not ones:
                return prefix
            if ones == 1 and tens > 1:
                return prefix + " mốt"
            if ones == 4 and tens > 1:
                return prefix + " tư"
            if ones == 5 and tens:
                return prefix + " lăm"
            return prefix + " " + digits[ones]

        def under_thousand(number: int) -> str:
            hundreds, remainder = divmod(number, 100)
            if not hundreds:
                return under_hundred(remainder)
            prefix = digits[hundreds] + " trăm"
            if not remainder:
                return prefix
            if remainder < 10:
                return prefix + " lẻ " + digits[remainder]
            return prefix + " " + under_hundred(remainder)

        def under_billion(number: int) -> str:
            millions, remainder = divmod(number, 1_000_000)
            if millions:
                result = under_thousand(millions) + " triệu"
                if remainder:
                    result += " " + under_billion(remainder)
                return result
            thousands, remainder = divmod(number, 1000)
            if thousands:
                result = under_thousand(thousands) + " nghìn"
                if remainder:
                    result += " " + under_thousand(remainder)
                return result
            return under_thousand(number)

        return under_billion(value)

    # Range diagnostics -------------------------------------------------

    def _out_of_range(self, value: int, number_format: str, *, display: str) -> str:
        key = (number_format, value)
        if key not in self._warned_ranges:
            self._warned_ranges.add(key)
            append_warning(
                self._warnings,
                "NUMBERING_VALUE_OUT_OF_RANGE",
                f"Word does not display numbering value {value} for {number_format}.",
                part="word/numbering.xml",
            )
        return display


__all__ = ["NumberFormatRenderer"]
