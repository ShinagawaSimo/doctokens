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

- [NumberFormatRenderer.format](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L47)
- [NumberFormatRenderer._format_custom](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L117)

## Conversion expressions

| `number_format` | Conversion expression |
| --- | --- |
| `aiueo` | `partial(_word_cycled_sequence, sequence=_AIUEO_HALF_WIDTH)` ([_word_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L54)) |
| `aiueoFullWidth` | `partial(_word_cycled_sequence, sequence=_AIUEO_FULL_WIDTH)` ([_word_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L54)) |
| `arabicAbjad` | `partial(_arabic_sequence, sequence=_ARABIC_ABJAD, prefix='\u200c')` ([_arabic_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L64)) |
| `arabicAlpha` | `partial(_arabic_sequence, sequence=_ARABIC_ALPHA, suffix='\u200c')` ([_arabic_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L64)) |
| `bahtText` | `str` |
| `bullet` | `str` |
| `cardinalText` | `_english_cardinal` ([_english_cardinal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_words.py#L8)) |
| `chicago` | `_chicago` ([_chicago](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L215)) |
| `chineseCounting` | `_chinese_counting` ([_chinese_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L88)) |
| `chineseCountingThousand` | `east_asian._chinese_counting_thousand` ([EastAsianNumberRenderer._chinese_counting_thousand](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L20)) |
| `chineseLegalSimplified` | `east_asian._chinese_legal_simplified` ([EastAsianNumberRenderer._chinese_legal_simplified](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L77)) |
| `chosung` | `partial(_word_cycled_sequence, sequence='ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ')` ([_word_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L54)) |
| `custom` | `_custom` ([_custom](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L25)) |
| `decimal` | `str` |
| `decimalEnclosedCircle` | `partial(_enclosed_decimal, start=9312, last=20)` ([_enclosed_decimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L78)) |
| `decimalEnclosedCircleChinese` | `partial(_enclosed_decimal, start=9312, last=10)` ([_enclosed_decimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L78)) |
| `decimalEnclosedFullstop` | `partial(_enclosed_decimal, start=9352, last=20)` ([_enclosed_decimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L78)) |
| `decimalEnclosedParen` | `partial(_enclosed_decimal, start=9332, last=20)` ([_enclosed_decimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L78)) |
| `decimalFullWidth` | `partial(_translate_digits, digits='０１２３４５６７８９')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `decimalFullWidth2` | `partial(_translate_digits, digits='０１２３４５６７８９')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `decimalHalfWidth` | `str` |
| `decimalZero` | `_decimal_zero` ([_decimal_zero](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L17)) |
| `dollarText` | `str` |
| `ganada` | `partial(_word_cycled_sequence, sequence='가나다라마바사아자차카타파하')` ([_word_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L54)) |
| `hebrew1` | `_hebrew_numeral` ([_hebrew_numeral](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L190)) |
| `hebrew2` | `_hebrew_alphabet` ([_hebrew_alphabet](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L208)) |
| `hex` | `_hexadecimal` ([_hexadecimal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L29)) |
| `hindiConsonants` | `partial(_word_repeated_sequence, sequence=(*tuple((chr(codepoint) for codepoint in range(2309, 2325))), 'अं', 'अः'))` ([_word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L47)) |
| `hindiCounting` | `_hindi_counting` ([_hindi_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_words.py#L95)) |
| `hindiNumbers` | `partial(_translate_digits, digits='०१२३४५६७८९')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `hindiVowels` | `partial(_word_repeated_sequence, sequence=''.join((chr(codepoint) for codepoint in range(2325, 2362))))` ([_word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L47)) |
| `ideographDigital` | `partial(_translate_digits, digits='〇一二三四五六七八九')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `ideographEnclosedCircle` | `_ideograph_enclosed_circle` ([_ideograph_enclosed_circle](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L82)) |
| `ideographLegalTraditional` | `east_asian._ideograph_legal_traditional` ([EastAsianNumberRenderer._ideograph_legal_traditional](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L86)) |
| `ideographTraditional` | `partial(_bounded_sequence, sequence='甲乙丙丁戊己庚辛壬癸')` ([_bounded_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L74)) |
| `ideographZodiac` | `partial(_bounded_sequence, sequence='子丑寅卯辰巳午未申酉戌亥')` ([_bounded_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L74)) |
| `ideographZodiacTraditional` | `_sexagenary_cycle` ([_sexagenary_cycle](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L181)) |
| `iroha` | `partial(_cycled_sequence, sequence=_IROHA_HALF_WIDTH)` ([_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L68)) |
| `irohaFullWidth` | `partial(_cycled_sequence, sequence=_IROHA_FULL_WIDTH)` ([_cycled_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L68)) |
| `japaneseCounting` | `east_asian._japanese_counting` ([EastAsianNumberRenderer._japanese_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L118)) |
| `japaneseDigitalTenThousand` | `partial(_translate_digits, digits='〇一二三四五六七八九')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `japaneseLegal` | `east_asian._japanese_legal` ([EastAsianNumberRenderer._japanese_legal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L158)) |
| `koreanCounting` | `east_asian._korean_counting` ([EastAsianNumberRenderer._korean_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L203)) |
| `koreanDigital` | `partial(_translate_digits, digits='영일이삼사오육칠팔구')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `koreanDigital2` | `partial(_translate_digits, digits='零一二三四五六七八九')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `koreanLegal` | `east_asian._korean_legal` ([EastAsianNumberRenderer._korean_legal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L210)) |
| `lowerLetter` | `partial(_word_letter_sequence, sequence='abcdefghijklmnopqrstuvwxyz')` ([_word_letter_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L60)) |
| `lowerRoman` | `lambda value: _roman(value).lower()` |
| `none` | `lambda _value: ''` |
| `numberInDash` | `_number_in_dash` ([_number_in_dash](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L21)) |
| `ordinal` | `_decimal_ordinal` ([_decimal_ordinal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L12)) |
| `ordinalText` | `_english_ordinal` ([_english_ordinal](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_words.py#L51)) |
| `russianLower` | `partial(_word_repeated_sequence, sequence=''.join((chr(codepoint) for codepoint in range(1072, 1081))) + ''.join((chr(codepoint) for codepoint in range(1082, 1088))) + ''.join((chr(codepoint) for codepoint in range(1088, 1098))) + 'ыэюя')` ([_word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L47)) |
| `russianUpper` | `partial(_word_repeated_sequence, sequence=''.join((chr(codepoint) for codepoint in range(1040, 1049))) + ''.join((chr(codepoint) for codepoint in range(1050, 1056))) + ''.join((chr(codepoint) for codepoint in range(1056, 1066))) + 'ЫЭЮЯ')` ([_word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L47)) |
| `taiwaneseCounting` | `east_asian._taiwanese_counting` ([EastAsianNumberRenderer._taiwanese_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L46)) |
| `taiwaneseCountingThousand` | `east_asian._taiwanese_counting_thousand` ([EastAsianNumberRenderer._taiwanese_counting_thousand](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_east_asian.py#L53)) |
| `taiwaneseDigital` | `partial(_translate_digits, digits='○一二三四五六七八九')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `thaiCounting` | `_thai_counting` ([_thai_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_words.py#L241)) |
| `thaiLetters` | `partial(_word_repeated_sequence, sequence='กขค' + ''.join((chr(codepoint) for codepoint in range(3591, 3620))) + 'ล' + ''.join((chr(codepoint) for codepoint in range(3623, 3631))))` ([_word_repeated_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L47)) |
| `thaiNumbers` | `partial(_translate_digits, digits='๐๑๒๓๔๕๖๗๘๙')` ([_translate_digits](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L37)) |
| `upperLetter` | `partial(_word_letter_sequence, sequence='ABCDEFGHIJKLMNOPQRSTUVWXYZ')` ([_word_letter_sequence](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L60)) |
| `upperRoman` | `_roman` ([_roman](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_sequences.py#L33)) |
| `vietnameseCounting` | `_vietnamese_counting` ([_vietnamese_counting](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/format_words.py#L267)) |
