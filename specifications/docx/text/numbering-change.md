# Numbering revisions

[DOCX](../README.md) / Numbering revisions

In the `original` revision view, `w:numberingChange` can provide level definitions for the paragraph’s saved numbering.

## Fields

### `original`

- **Output**
  - Previous marker definition.

- **OOXML**
  - `w:pPr/w:numPr/w:numberingChange/@w:original`

- **IR**
  - `dict[int, NumberingLevel]`

- **Parsing**
  - Find definitions with `(?<!%)%([0-9]+):([0-9]+):([^:]+):`. Text from the end of a match to the next match is its separator; text before the first match is the first prefix.

- **Absence and defaults**
  - Absent or empty: `{}`.

- **Diagnostics**
  - No matches: `INVALID_NUMBERING_CHANGE`, empty result.

### `level`

- **Output**
  - Zero-based override key.

- **OOXML**
  - First numeric capture.

- **IR**
  - `NumberingLevel.numbering_level: int`

- **Parsing**
  - `max(0, int(level_number) - 1)`; later duplicate indices replace earlier ones.

### `nfc`

- **Output**
  - Numeric format selector.

- **OOXML**
  - Second numeric capture.

- **IR**
  - Lookup in `NumberFormatRenderer._NFC_FORMATS`.

- **Parsing**
  - Use the exact mapping in [NumberFormatRenderer](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/formats.py#L32). An unknown selector skips its definition.

- **Diagnostics**
  - `40` or `>=60`: `APPLICATION_DEFINED_NUMBER_FORMAT`; other unknown values: `INVALID_NUMBERING_CHANGE`.

### `format`

- **Output**
  - Resolved number format.

- **OOXML**
  - Third capture.

- **IR**
  - `NumberingLevel.number_format: str`

- **Parsing**
  - Keep the captured format only if it occurs among NFC mapping values; otherwise use the NFC-mapped format.

### `template`

- **Output**
  - Previous marker template.

- **OOXML**
  - Prefix, level number, separator.

- **IR**
  - `NumberingLevel.level_text: str`

- **Parsing**
  - `f"{prefix}%{level_number}{separator}"`; only the first matched definition receives the prefix. Construct levels with `suffix="nothing"`; other fields retain `NumberingLevel` defaults.

- **Diagnostics**
  - Significant length is prefix plus accepted level placeholders and separators after replacing `%%` with `%`. Length >31: `INVALID_NUMBERING_CHANGE` and discard all overrides.


## Source references

- [parse_numbering_change](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/change.py#L12)
- [ParagraphNumbering.parse](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/numbering.py#L39)
