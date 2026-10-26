"""Format codes."""

from __future__ import annotations

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


_NFC_FORMATS: dict[int, str] = {
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
