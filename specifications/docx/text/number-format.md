# Number conversion

[DOCX](../README.md) / Number conversion

Number conversion maps a counter to characters before the marker template adds punctuation and spacing.

## Processing

The following upper limits return `""` and `NUMBERING_VALUE_OUT_OF_RANGE` when exceeded, unless the earlier universal limit has already returned:

| Formats | Maximum |
| --- | ---: |
| `cardinalText`, `chineseCountingThousand`, `chineseLegalSimplified`, `ideographLegalTraditional`, `japaneseCounting`, `koreanCounting`, `koreanDigital2`, `ordinalText`, `taiwaneseCountingThousand` | 999,999 |
| `japaneseDigitalTenThousand` | 9,999 |
| `hex` | 65,535 |
| `koreanLegal` | 9,999,999 |

## Fields

### `value`

- **Output**
  - Textual counter.

- **OOXML**
  - Counter state and `w:start`.

- **IR**
  - `NumberFormatRenderer.format(value: int, ...) -> str`

- **Parsing**
  - `value > 217_483_647` returns `""` without a warning. Smaller values follow the selected conversion; there is no universal positive-value clamp.

### `number_format`

- **Output**
  - Selects the conversion expression below.

- **OOXML**
  - `w:numFmt/@w:val`

- **IR**
  - `NumberingLevel.number_format: str`

- **Parsing**
  - Unknown format: `str(value)`. `cardinalText`, `ordinal`, `ordinalText`, `upperLetter`, and `lowerLetter` first apply the language rules. Other names use the conversion table.

- **Absence and defaults**
  - Default `"decimal"`.

- **Diagnostics**
  - `UNSUPPORTED_NUMBER_FORMAT` once per unknown format. `NUMBERING_VALUE_OUT_OF_RANGE` for format-specific range failures; the affected converter determines the replacement text.

### `language`

- **Output**
  - Language-specific cardinal, ordinal, and alphabetic text.

- **OOXML**
  - `w:rPr/w:lang`

- **IR**
  - `NumberingLevel.language: str | None`

- **Parsing**
  - Dispatch through [language.py](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/language.py). Unrecognized languages use the formatter’s English cardinal/ordinal or Latin alphabet fallback. The language does not change the counter value.

### `custom_format`

- **Output**
  - Pattern prefix + converted token + pattern suffix.

- **OOXML**
  - `w:numFmt/@w:format`

- **IR**
  - `NumberingLevel.custom_format: str | None`

- **Parsing**
  - After range checks, evaluate a truthy custom pattern before the named format. `ア` and `ｱ` select the corresponding Japanese cycle. Otherwise find the first `[A-Za-z0-9]+` token whose characters are contained in `01AaIi`. A token made of `0`/`1` and containing `1` zero-pads to token length; repeated `A`, `a`, `I`, or `i` selects letters or Roman numerals. Mixed tokens fail. Preserve all text before and after that token.

- **Absence and defaults**
  - For `number_format="custom"`, missing or unsupported pattern falls back to decimal.

- **Diagnostics**
  - `UNSUPPORTED_CUSTOM_NUMBER_FORMAT`, deduplicated by pattern and fallback name.


## Source references

- [NumberFormatRenderer.format](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L134)
- [NumberFormatRenderer._format_custom](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L312)

## Conversion expressions

| `number_format` | Conversion expression |
| --- | --- |
| `aiueo` | `partial(self._word_cycled_sequence, sequence=self._AIUEO_HALF_WIDTH)` ([NumberFormatRenderer._word_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L404)) |
| `aiueoFullWidth` | `partial(self._word_cycled_sequence, sequence=self._AIUEO_FULL_WIDTH)` ([NumberFormatRenderer._word_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L404)) |
| `arabicAbjad` | `partial(self._arabic_sequence, sequence=self._ARABIC_ABJAD, prefix='\u200c')` ([NumberFormatRenderer._arabic_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L414)) |
| `arabicAlpha` | `partial(self._arabic_sequence, sequence=self._ARABIC_ALPHA, suffix='\u200c')` ([NumberFormatRenderer._arabic_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L414)) |
| `bahtText` | `str` |
| `bullet` | `str` |
| `cardinalText` | `self._english_cardinal` ([NumberFormatRenderer._english_cardinal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L801)) |
| `chicago` | `self._chicago` ([NumberFormatRenderer._chicago](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L791)) |
| `chineseCounting` | `self._chinese_counting` ([NumberFormatRenderer._chinese_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L440)) |
| `chineseCountingThousand` | `self._chinese_counting_thousand` ([NumberFormatRenderer._chinese_counting_thousand](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L452)) |
| `chineseLegalSimplified` | `self._chinese_legal_simplified` ([NumberFormatRenderer._chinese_legal_simplified](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L546)) |
| `chosung` | `partial(self._word_cycled_sequence, sequence='ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ')` ([NumberFormatRenderer._word_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L404)) |
| `custom` | `self._custom` ([NumberFormatRenderer._custom](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L309)) |
| `decimal` | `str` |
| `decimalEnclosedCircle` | `partial(self._enclosed_decimal, start=9312, last=20)` ([NumberFormatRenderer._enclosed_decimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L428)) |
| `decimalEnclosedCircleChinese` | `partial(self._enclosed_decimal, start=9312, last=10)` ([NumberFormatRenderer._enclosed_decimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L428)) |
| `decimalEnclosedFullstop` | `partial(self._enclosed_decimal, start=9352, last=20)` ([NumberFormatRenderer._enclosed_decimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L428)) |
| `decimalEnclosedParen` | `partial(self._enclosed_decimal, start=9332, last=20)` ([NumberFormatRenderer._enclosed_decimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L428)) |
| `decimalFullWidth` | `partial(self._translate_digits, digits='０１２３４５６７８９')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `decimalFullWidth2` | `partial(self._translate_digits, digits='０１２３４５６７８９')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `decimalHalfWidth` | `str` |
| `decimalZero` | `self._decimal_zero` ([NumberFormatRenderer._decimal_zero](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L302)) |
| `dollarText` | `str` |
| `ganada` | `partial(self._word_cycled_sequence, sequence='가나다라마바사아자차카타파하')` ([NumberFormatRenderer._word_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L404)) |
| `hebrew1` | `self._hebrew_numeral` ([NumberFormatRenderer._hebrew_numeral](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L766)) |
| `hebrew2` | `self._hebrew_alphabet` ([NumberFormatRenderer._hebrew_alphabet](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L784)) |
| `hex` | `self._hexadecimal` ([NumberFormatRenderer._hexadecimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L377)) |
| `hindiConsonants` | `partial(self._word_repeated_sequence, sequence=(*tuple((chr(codepoint) for codepoint in range(2309, 2325))), 'अं', 'अः'))` ([NumberFormatRenderer._word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L397)) |
| `hindiCounting` | `self._hindi_counting` ([NumberFormatRenderer._hindi_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L888)) |
| `hindiNumbers` | `partial(self._translate_digits, digits='०१२३४५६७८९')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `hindiVowels` | `partial(self._word_repeated_sequence, sequence=''.join((chr(codepoint) for codepoint in range(2325, 2362))))` ([NumberFormatRenderer._word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L397)) |
| `ideographDigital` | `partial(self._translate_digits, digits='〇一二三四五六七八九')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `ideographEnclosedCircle` | `self._ideograph_enclosed_circle` ([NumberFormatRenderer._ideograph_enclosed_circle](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L432)) |
| `ideographLegalTraditional` | `self._ideograph_legal_traditional` ([NumberFormatRenderer._ideograph_legal_traditional](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L555)) |
| `ideographTraditional` | `partial(self._bounded_sequence, sequence='甲乙丙丁戊己庚辛壬癸')` ([NumberFormatRenderer._bounded_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L424)) |
| `ideographZodiac` | `partial(self._bounded_sequence, sequence='子丑寅卯辰巳午未申酉戌亥')` ([NumberFormatRenderer._bounded_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L424)) |
| `ideographZodiacTraditional` | `self._sexagenary_cycle` ([NumberFormatRenderer._sexagenary_cycle](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L755)) |
| `iroha` | `partial(self._cycled_sequence, sequence=self._IROHA_HALF_WIDTH)` ([NumberFormatRenderer._cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L418)) |
| `irohaFullWidth` | `partial(self._cycled_sequence, sequence=self._IROHA_FULL_WIDTH)` ([NumberFormatRenderer._cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L418)) |
| `japaneseCounting` | `self._japanese_counting` ([NumberFormatRenderer._japanese_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L587)) |
| `japaneseDigitalTenThousand` | `partial(self._translate_digits, digits='〇一二三四五六七八九')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `japaneseLegal` | `self._japanese_legal` ([NumberFormatRenderer._japanese_legal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L627)) |
| `koreanCounting` | `self._korean_counting` ([NumberFormatRenderer._korean_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L672)) |
| `koreanDigital` | `partial(self._translate_digits, digits='영일이삼사오육칠팔구')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `koreanDigital2` | `partial(self._translate_digits, digits='零一二三四五六七八九')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `koreanLegal` | `self._korean_legal` ([NumberFormatRenderer._korean_legal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L722)) |
| `lowerLetter` | `partial(self._word_letter_sequence, sequence='abcdefghijklmnopqrstuvwxyz')` ([NumberFormatRenderer._word_letter_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L410)) |
| `lowerRoman` | `lambda value: self._roman(value).lower()` |
| `none` | `lambda _value: ''` |
| `numberInDash` | `self._number_in_dash` ([NumberFormatRenderer._number_in_dash](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L306)) |
| `ordinal` | `self._decimal_ordinal` ([NumberFormatRenderer._decimal_ordinal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L297)) |
| `ordinalText` | `self._english_ordinal` ([NumberFormatRenderer._english_ordinal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L844)) |
| `russianLower` | `partial(self._word_repeated_sequence, sequence=''.join((chr(codepoint) for codepoint in range(1072, 1081))) + ''.join((chr(codepoint) for codepoint in range(1082, 1088))) + ''.join((chr(codepoint) for codepoint in range(1088, 1098))) + 'ыэюя')` ([NumberFormatRenderer._word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L397)) |
| `russianUpper` | `partial(self._word_repeated_sequence, sequence=''.join((chr(codepoint) for codepoint in range(1040, 1049))) + ''.join((chr(codepoint) for codepoint in range(1050, 1056))) + ''.join((chr(codepoint) for codepoint in range(1056, 1066))) + 'ЫЭЮЯ')` ([NumberFormatRenderer._word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L397)) |
| `taiwaneseCounting` | `self._taiwanese_counting` ([NumberFormatRenderer._taiwanese_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L478)) |
| `taiwaneseCountingThousand` | `self._taiwanese_counting_thousand` ([NumberFormatRenderer._taiwanese_counting_thousand](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L485)) |
| `taiwaneseDigital` | `partial(self._translate_digits, digits='○一二三四五六七八九')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `thaiCounting` | `self._thai_counting` ([NumberFormatRenderer._thai_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L1034)) |
| `thaiLetters` | `partial(self._word_repeated_sequence, sequence='กขค' + ''.join((chr(codepoint) for codepoint in range(3591, 3620))) + 'ล' + ''.join((chr(codepoint) for codepoint in range(3623, 3631))))` ([NumberFormatRenderer._word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L397)) |
| `thaiNumbers` | `partial(self._translate_digits, digits='๐๑๒๓๔๕๖๗๘๙')` ([NumberFormatRenderer._translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L385)) |
| `upperLetter` | `partial(self._word_letter_sequence, sequence='ABCDEFGHIJKLMNOPQRSTUVWXYZ')` ([NumberFormatRenderer._word_letter_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L410)) |
| `upperRoman` | `self._roman` ([NumberFormatRenderer._roman](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L381)) |
| `vietnameseCounting` | `self._vietnamese_counting` ([NumberFormatRenderer._vietnamese_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L1060)) |
