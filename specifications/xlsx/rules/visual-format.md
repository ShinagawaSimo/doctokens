# Conditional visual formats

[XLSX](../README.md) / Conditional visual formats

Visual-format dictionaries retain source strings.

## Fields

### `stops`

- **Output**
  - Semantic details string.

- **OOXML**
  - colorScale/cfvo and color children.

- **IR**
  - `formatDetails["stops"]: list[dict[str,str]]`

- **Parsing**
  - Pair by position. Each cfvo retains type/val/gte; paired color chooses rgb then theme then indexed. Missing color leaves threshold only.

### `thresholds`

- **Output**
  - Semantic details string.

- **OOXML**
  - dataBar/cfvo or iconSet/cfvo.

- **IR**
  - `list[dict[str,str]]`

- **Parsing**
  - Keep direct cfvo children, preserving type/val/gte if present.

### `type`

- **Output**
  - Stop/threshold field.

- **OOXML**
  - cfvo/@type.

- **IR**
  - `str`

- **Parsing**
  - Copy source discriminator without evaluating it.

### `val`

- **Output**
  - Stop/threshold field.

- **OOXML**
  - cfvo/@val.

- **IR**
  - `str`

- **Parsing**
  - Copy literal/formula string.

### `gte`

- **Output**
  - Stop/threshold field.

- **OOXML**
  - cfvo/@gte.

- **IR**
  - `str`

- **Parsing**
  - Copy present source string; no synthesized default.

### `color`

- **Output**
  - Stop/bar field.

- **OOXML**
  - color/@rgb, @theme, @indexed.

- **IR**
  - `str`

- **Parsing**
  - First truthy in that order; color references are not resolved here.

### `minLength`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@minLength.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `maxLength`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@maxLength.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `showValue`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@showValue.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `gradient`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@gradient.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `border`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@border.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `direction`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@direction.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `iconSet attributes`

- **Output**
  - Semantic details fields.

- **OOXML**
  - All iconSet attributes.

- **IR**
  - `dict[str,object]`

- **Parsing**
  - Copy complete attribute dictionary; add thresholds. Attribute vocabulary is open and source-defined.


## Source references

- [_conditional_format_detail](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L508)
- [_format_thresholds](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L553)
