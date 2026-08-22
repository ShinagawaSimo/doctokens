"""Render the visible value of Word ``w:numFmt`` numbering formats.

The OOXML numbering model owns counter state and level inheritance.  This
module deliberately owns only number-to-text conversion, so adding a new
format cannot accidentally change list restart behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
from types import MappingProxyType

from ..core.models import ParseWarning, append_warning


class NumberFormatRenderer:
    """Format individual numbering values and report unsupported formats once."""

    _ARABIC_ALPHA = "أبتثجحخدذرزسشصضطظعغفقكلمنهوي"
    _ARABIC_ABJAD = "أبجدهوزحطيكلمنسعفصقرشتثخذضظغ"
    _HEBREW_ALPHABET = "אבגדהוזחטיכלמנסעפצקרשת"
    _AIUEO_HALF_WIDTH = (
        "\uFF71\uFF72\uFF73\uFF74\uFF75\uFF76\uFF77\uFF78\uFF79\uFF7A"
        "\uFF7B\uFF7C\uFF7D\uFF7E\uFF7F\uFF80\uFF81\uFF82\uFF83\uFF84"
        "\uFF85\uFF86\uFF87\uFF88\uFF89\uFF8A\uFF8B\uFF8C\uFF8D\uFF8E"
        "\uFF8F\uFF90\uFF91\uFF92\uFF93\uFF94\uFF95\uFF96\uFF97\uFF98"
        "\uFF99\uFF9A\uFF9B\uFF9C\uFF66\uFF9D"
    )
    _IROHA_HALF_WIDTH = (
        "\uFF72\uFF9B\uFF8A\uFF86\uFF8E\uFF8D\uFF84\uFF81\uFF98\uFF87"
        "\uFF99\uFF66\uFF9C\uFF76\uFF96\uFF80\uFF9A\uFF7F\uFF82\uFF88"
        "\uFF85\uFF97\uFF91\uFF73\u30F0\uFF89\uFF75\uFF78\uFF94\uFF8F"
        "\uFF79\uFF8C\uFF7A\uFF74\uFF83\uFF71\uFF7B\uFF77\uFF95\uFF92"
        "\uFF90\uFF7C\u30F1\uFF8B\uFF93\uFF7E\uFF7D\uFF9D"
    )

    def __init__(self, warnings: list[ParseWarning]) -> None:
        self._warnings = warnings
        self._warned_formats: set[str] = set()
        self._formatters: Mapping[str, Callable[[int], str]] = MappingProxyType(self._build_formatters())

    def format(self, value: int, number_format: str) -> str:
        """Convert *value* to visible numbering text for one ``w:numFmt`` value."""
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

    def _build_formatters(self) -> dict[str, Callable[[int], str]]:
        """Register the ``ST_NumberFormat`` values with deterministic renderers."""
        return {
            "decimal": str,
            "decimalHalfWidth": str,
            "ordinal": self._decimal_ordinal,
            "decimalZero": self._decimal_zero,
            "decimalFullWidth": partial(self._translate_decimal_digits, digits="０１２３４５６７８９"),
            "decimalFullWidth2": partial(self._translate_decimal_digits, digits="０１２３４５６７８９"),
            "hindiNumbers": partial(self._translate_decimal_digits, digits="०१२३४५६७८९"),
            "thaiNumbers": partial(self._translate_decimal_digits, digits="๐๑๒๓๔๕๖๗๘๙"),
            "lowerLetter": partial(
                self._bounded_repeated_sequence,
                sequence="abcdefghijklmnopqrstuvwxyz",
                maximum=780,
            ),
            "upperLetter": partial(
                self._bounded_repeated_sequence,
                sequence="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                maximum=780,
            ),
            "upperRoman": lambda value: self._roman(value).upper(),
            "lowerRoman": lambda value: self._roman(value).lower(),
            "hex": lambda value: f"{value:X}",
            "cardinalText": self._english_cardinal,
            "ordinalText": self._english_ordinal,
            "numberInDash": self._number_in_dash,
            "chicago": self._chicago,
            "bahtText": str,
            "dollarText": str,
            "decimalEnclosedCircle": lambda value: self._enclosed_decimal(value, (0x2460,)),
            "decimalEnclosedFullstop": lambda value: self._enclosed_decimal(value, (0x2488,)),
            "decimalEnclosedParen": lambda value: self._enclosed_decimal(value, (0x2474,)),
            "decimalEnclosedCircleChinese": self._chinese_circled_decimal,
            "ideographEnclosedCircle": self._enclosed_ideograph,
            "ganada": partial(self._cycled_sequence, sequence="가나다라마바사아자차카타파하"),
            "chosung": partial(self._cycled_sequence, sequence="ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"),
            "aiueo": partial(
                self._cycled_sequence,
                sequence=self._AIUEO_HALF_WIDTH,
            ),
            "aiueoFullWidth": partial(
                self._cycled_sequence,
                sequence="アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン",
            ),
            "iroha": partial(
                self._cycled_sequence,
                sequence=self._IROHA_HALF_WIDTH,
            ),
            "irohaFullWidth": partial(
                self._cycled_sequence,
                sequence="イロハニホヘトチリヌルヲワカヨタレソツネナラムウヰノオクヤマケフコエテアサキユメミシヱヒモセス",
            ),
            "hindiVowels": partial(self._repeated_sequence, sequence="कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह"),
            "hindiConsonants": partial(self._repeated_sequence, sequence="अआइईउऊऋएऐओऔअंअः"),
            "thaiLetters": partial(self._repeated_sequence, sequence="กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรฤลฦวศษสหฬอฮ"),
            "russianLower": partial(self._repeated_sequence, sequence="абвгдежзийклмнопрстуфхцчшщъыьэюя"),
            "russianUpper": partial(self._repeated_sequence, sequence="АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"),
            "arabicAlpha": self._arabic_alpha,
            "arabicAbjad": self._arabic_abjad,
            "hebrew1": self._hebrew_numeral,
            "hebrew2": partial(self._repeated_sequence, sequence=self._HEBREW_ALPHABET),
            "ideographTraditional": partial(self._bounded_sequence, sequence="甲乙丙丁戊己庚辛壬癸"),
            "ideographZodiac": partial(self._bounded_sequence, sequence="子丑寅卯辰巳午未申酉戌亥"),
            "ideographZodiacTraditional": self._sexagenary_cycle,
            "ideographDigital": self._chinese_digital,
            "taiwaneseDigital": partial(self._translate_decimal_digits, digits="零一二三四五六七八九"),
            "chineseCounting": partial(
                self._limited_east_asian,
                format_name="Chinese counting",
                digits="〇一二三四五六七八九",
                small_units="十百千",
                large_unit="万",
            ),
            "chineseCountingThousand": partial(
                self._limited_east_asian,
                format_name="Chinese counting",
                digits="〇一二三四五六七八九",
                small_units="十百千",
                large_unit="万",
            ),
            "taiwaneseCounting": partial(
                self._limited_east_asian,
                format_name="Taiwanese counting",
                digits="零一二三四五六七八九",
                small_units="十百千",
                large_unit="萬",
            ),
            "taiwaneseCountingThousand": partial(
                self._limited_east_asian,
                format_name="Taiwanese counting",
                digits="零一二三四五六七八九",
                small_units="十百千",
                large_unit="萬",
            ),
            "chineseLegalSimplified": partial(
                self._limited_east_asian,
                format_name="Chinese legal",
                digits="零壹貳叁肆伍陸柒捌玖",
                small_units="拾佰仟",
                large_unit="萬",
                omit_one_ten=False,
            ),
            "ideographLegalTraditional": partial(
                self._limited_east_asian,
                format_name="traditional legal ideograph",
                digits="零壹貳參肆伍陸柒捌玖",
                small_units="拾佰仟",
                large_unit="萬",
                omit_one_ten=False,
            ),
            "japaneseCounting": partial(
                self._limited_japanese_counting,
                format_name="Japanese counting",
            ),
            "japaneseDigitalTenThousand": self._chinese_digital,
            "japaneseLegal": partial(
                self._limited_japanese_legal,
                format_name="Japanese legal",
            ),
            "koreanDigital": partial(self._translate_decimal_digits, digits="영일이삼사오육칠팔구"),
            "koreanCounting": partial(
                self._limited_east_asian,
                format_name="Korean counting",
                digits="영일이삼사오육칠팔구",
                small_units="십백천",
                large_unit="만",
            ),
            "none": lambda _value: "",
        }

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

    @staticmethod
    def _chicago(value: int) -> str:
        """Render Chicago note-reference symbols in the conventional six-symbol cycle."""
        if value <= 0:
            return str(value)
        symbol = ("*", "†", "‡", "§", "‖", "#")[(value - 1) % 6]
        return symbol * ((value - 1) // 6 + 1)

    def _arabic_alpha(self, value: int) -> str:
        return self._repeated_sequence(value, self._ARABIC_ALPHA) + "\u200c"

    def _arabic_abjad(self, value: int) -> str:
        return "\u200c" + self._repeated_sequence(value, self._ARABIC_ABJAD)

    @staticmethod
    def _hebrew_numeral(value: int) -> str:
        """Render additive Hebrew numerals without adding punctuation from ``lvlText``."""
        if value <= 0 or value > 999:
            return str(value)
        hundreds, remainder = divmod(value, 100)
        parts = "ת" * (hundreds // 4)
        if hundreds % 4:
            parts += ("", "ק", "ר", "ש")[hundreds % 4]
        if remainder in {15, 16}:
            return parts + ("טו" if remainder == 15 else "טז")
        tens, units = divmod(remainder, 10)
        tens_glyph = ("", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ")[tens]
        units_glyph = ("", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט")[units]
        return parts + tens_glyph + units_glyph

    @staticmethod
    def _chinese_circled_decimal(value: int) -> str:
        return chr(0x2460 + value - 1) if 1 <= value <= 10 else str(value)

    @staticmethod
    def _enclosed_ideograph(value: int) -> str:
        return chr(0x3220 + value - 1) if 1 <= value <= 10 else str(value)

    @staticmethod
    def _chinese_digital(value: int) -> str:
        if value < 0:
            return str(value)
        digits = "〇一二三四五六七八九"
        return "".join(digits[int(character)] for character in str(value))

    def _limited_east_asian(
        self,
        value: int,
        *,
        format_name: str,
        digits: str,
        small_units: str,
        large_unit: str,
        omit_one_ten: bool = True,
        word_thousand_rules: bool = False,
    ) -> str:
        if value > 999_999:
            return self._numbering_out_of_range(value, format_name)
        return self._east_asian_counting(
            value,
            digits,
            small_units,
            large_unit,
            omit_one_ten=omit_one_ten,
            word_thousand_rules=word_thousand_rules,
        )

    def _limited_japanese_counting(self, value: int, *, format_name: str) -> str:
        if value > 999_999:
            return self._numbering_out_of_range(value, format_name)
        return self._japanese_counting(value)

    def _limited_japanese_legal(self, value: int, *, format_name: str) -> str:
        if value > 999_999:
            return self._numbering_out_of_range(value, format_name)
        return self._japanese_legal(value)

    def _numbering_out_of_range(self, value: int, format_name: str) -> str:
        append_warning(
            self._warnings,
            "NUMBERING_VALUE_OUT_OF_RANGE",
            f"Numbering value {value} exceeds the supported {format_name} range; decimal fallback is used.",
            part="word/numbering.xml",
        )
        return str(value)

    @staticmethod
    def _repeated_sequence(value: int, sequence: str) -> str:
        if value <= 0 or not sequence:
            return str(value)
        index, repetition = divmod(value - 1, len(sequence))
        return sequence[repetition] * (index + 1)

    @staticmethod
    def _bounded_repeated_sequence(value: int, sequence: str, maximum: int) -> str:
        if value > maximum:
            return str(value)
        return NumberFormatRenderer._repeated_sequence(value, sequence)

    @staticmethod
    def _cycled_sequence(value: int, sequence: str) -> str:
        if value <= 0 or not sequence:
            return str(value)
        return sequence[(value - 1) % len(sequence)]

    @staticmethod
    def _bounded_sequence(value: int, sequence: str) -> str:
        if 1 <= value <= len(sequence):
            return sequence[value - 1]
        return str(value)

    @staticmethod
    def _sexagenary_cycle(value: int) -> str:
        if value <= 0:
            return str(value)
        stems = "甲乙丙丁戊己庚辛壬癸"
        branches = "子丑寅卯辰巳午未申酉戌亥"
        index = value - 1
        return stems[index % len(stems)] + branches[index % len(branches)]

    @staticmethod
    def _translate_decimal_digits(value: int, digits: str) -> str:
        return "".join(digits[int(character)] if character.isdigit() else character for character in str(value))

    @staticmethod
    def _enclosed_decimal(value: int, starts: tuple[int, ...]) -> str:
        ranges = ((1, 20), (21, 35), (36, 50))
        for start, (first, last) in zip(starts, ranges, strict=False):
            if first <= value <= last:
                return chr(start + value - first)
        return str(value)

    @staticmethod
    def _roman(value: int) -> str:
        if value <= 0:
            return str(value)
        pairs = (
            (1000, "M"),
            (900, "CM"),
            (500, "D"),
            (400, "CD"),
            (100, "C"),
            (90, "XC"),
            (50, "L"),
            (40, "XL"),
            (10, "X"),
            (9, "IX"),
            (5, "V"),
            (4, "IV"),
            (1, "I"),
        )
        result: list[str] = []
        for amount, glyph in pairs:
            quotient, value = divmod(value, amount)
            result.append(glyph * quotient)
        return "".join(result)

    @staticmethod
    def _chinese_counting(value: int, *, word_thousand_rules: bool = False) -> str:
        return NumberFormatRenderer._east_asian_counting(
            value,
            "〇一二三四五六七八九",
            "十百千",
            "万",
            word_thousand_rules=word_thousand_rules,
        )

    @staticmethod
    def _japanese_counting(value: int) -> str:
        """Render Japanese counting, which omits ``一`` before 十/百/千 and zeros."""
        digits = "〇一二三四五六七八九"
        small_units = "十百千"
        if value == 0:
            return digits[0]
        if value < 0 or value > 999_999:
            return str(value)

        def section(number: int) -> str:
            parts: list[str] = []
            for divisor, unit in ((1000, small_units[2]), (100, small_units[1]), (10, small_units[0])):
                digit, number = divmod(number, divisor)
                if digit:
                    if digit != 1:
                        parts.append(digits[digit])
                    parts.append(unit)
            if number:
                parts.append(digits[number])
            return "".join(parts)

        high, low = divmod(value, 10_000)
        if not high:
            return section(low)
        result = section(high) + "万"
        return result if not low else result + section(low)

    @staticmethod
    def _japanese_legal(value: int) -> str:
        """Render Japanese legal numbering without zeroes or omitted unit ones."""
        digits = "〇壱弐参四伍六七八九"
        small_units = "拾百阡"
        if value == 0:
            return digits[0]
        if value < 0 or value > 999_999:
            return str(value)

        def section(number: int) -> str:
            parts: list[str] = []
            for divisor, unit in ((1000, small_units[2]), (100, small_units[1]), (10, small_units[0])):
                digit, number = divmod(number, divisor)
                if digit:
                    parts.append(digits[digit])
                    parts.append(unit)
            if number:
                parts.append(digits[number])
            return "".join(parts)

        high, low = divmod(value, 10_000)
        if not high:
            return section(low)
        result = section(high) + "萬"
        return result if not low else result + section(low)

    @staticmethod
    def _east_asian_counting(
        value: int,
        digits: str,
        small_units: str,
        large_unit: str,
        *,
        omit_one_ten: bool = True,
        word_thousand_rules: bool = False,
    ) -> str:
        if value == 0:
            return digits[0]
        if value < 0 or value > 999_999:
            return str(value)

        def section(number: int, *, omit_initial_one: bool) -> str:
            parts: list[str] = []
            pending_zero = False
            for divisor, unit in ((1000, small_units[2]), (100, small_units[1]), (10, small_units[0])):
                digit, remainder = divmod(number, divisor)
                if digit:
                    if pending_zero:
                        parts.append(digits[0])
                        pending_zero = False
                    if not (divisor == 10 and digit == 1 and not parts and omit_initial_one):
                        parts.append(digits[digit])
                    parts.append(unit)
                elif parts and remainder:
                    pending_zero = True
                number = remainder
            if number:
                if pending_zero:
                    parts.append(digits[0])
                parts.append(digits[number])
            return "".join(parts)

        high, low = divmod(value, 10_000)
        if not high:
            return section(low, omit_initial_one=omit_one_ten)
        result = section(high, omit_initial_one=omit_one_ten) + large_unit
        if not low:
            return result
        if low < 1000 and not word_thousand_rules:
            result += digits[0]
        return result + section(low, omit_initial_one=False)

    @staticmethod
    def _english_cardinal(value: int) -> str:
        if value < 0 or value > 999_999:
            return str(value)
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
                ten, rest = divmod(number, 10)
                return tens[ten] if not rest else f"{tens[ten]}-{ones[rest]}"
            hundred, rest = divmod(number, 100)
            return f"{ones[hundred]} hundred" if not rest else f"{ones[hundred]} hundred {under_thousand(rest)}"

        if value < 1000:
            return under_thousand(value).title()
        thousands, rest = divmod(value, 1000)
        rendered = (
            f"{under_thousand(thousands)} thousand"
            if not rest
            else f"{under_thousand(thousands)} thousand {under_thousand(rest)}"
        )
        return rendered.title()

    @classmethod
    def _english_ordinal(cls, value: int) -> str:
        if value < 0 or value > 999_999:
            return str(value)
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
            return prefix + separator + special.get(tail, tail + "th")
        prefix, separator, tail = cardinal.rpartition(" ")
        ordinal_tail = special.get(tail, tail + "th")
        return (prefix + separator + ordinal_tail if separator else ordinal_tail).title()


__all__ = ["NumberFormatRenderer"]
