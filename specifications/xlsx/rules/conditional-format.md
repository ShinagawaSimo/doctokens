# Conditional formatting

[XLSX](../README.md) / Conditional formatting

Rules describe conditions and formatting; they do not calculate effective per-cell styles.

## Fields

### `ranges`

- **Output**
  - conditional-format/@ref

- **OOXML**
  - `s:conditionalFormatting/@sqref`

- **IR**
  - `ConditionalFormat.ranges`

- **Parsing**
  - Copy, default empty; one container per parsed rule.

### `priority`

- **Output**
  - rule/@priority

- **OOXML**
  - `s:cfRule/@priority`

- **IR**
  - `ConditionalFormat.priority`

- **Parsing**
  - int, default/failure 0; source order retained without priority sorting.

### `ruleType`

- **Output**
  - rule/@type

- **OOXML**
  - `s:cfRule/@type`

- **IR**
  - `ConditionalFormat.ruleType`

- **Parsing**
  - Copy, default empty.

### `formulas`

- **Output**
  - rule/@formula or @formulas

- **OOXML**
  - `s:cfRule/s:formula/text()`

- **IR**
  - `ConditionalFormat.formulas`

- **Parsing**
  - One → formula; several → join with ` | ` as formulas; none → omit.

### `dxfId`

- **Output**
  - rule/@dxf

- **OOXML**
  - `s:cfRule/@dxfId`

- **IR**
  - `ConditionalFormat.dxfId`

- **Parsing**
  - Present → int, failure 0.

### `stopIfTrue`

- **Output**
  - rule/@stop-if-true

- **OOXML**
  - `s:cfRule/@stopIfTrue`

- **IR**
  - `ConditionalFormat.stopIfTrue`

- **Parsing**
  - Exactly 1 → true; DTX omits false.

### `operator`

- **Output**
  - rule/@operator

- **OOXML**
  - `s:cfRule/@operator`

- **IR**
  - `ConditionalFormat.operator`

- **Parsing**
  - Copy nonempty.

### `text`

- **Output**
  - rule/@text

- **OOXML**
  - `s:cfRule/@text`

- **IR**
  - `ConditionalFormat.text`

- **Parsing**
  - Copy nonempty.

### `rank`

- **Output**
  - rule/@rank

- **OOXML**
  - `s:cfRule/@rank`

- **IR**
  - `ConditionalFormat.rank`

- **Parsing**
  - Nonempty → int, failure 0.

### `percent`

- **Output**
  - rule/@percent

- **OOXML**
  - `s:cfRule/@percent`

- **IR**
  - `ConditionalFormat.percent`

- **Parsing**
  - Store/output only true for 1.

### `formatKind`

- **Output**
  - rule/@format

- **OOXML**
  - `s:cfRule/s:colorScale`, `s:cfRule/s:dataBar`, `s:cfRule/s:iconSet`.

- **IR**
  - `ConditionalFormat.formatKind`

- **Parsing**
  - First recognized child local name.

### `formatDetails`

- **Output**
  - Semantic rule/@details

- **OOXML**
  - The child selected by `formatKind`.

- **IR**
  - `ConditionalFormat.formatDetails`

- **Parsing**
  - See [visual rules](visual-format.md). Serialize scalar key=value; stops/thresholds records use colon-separated fields and semicolon-separated entries; then join top-level items with semicolon.

### `dxfStyle`

- **Output**
  - rule/@style

- **OOXML**
  - `xl/styles.xml`: `s:styleSheet/s:dxfs/s:dxf`, selected by zero-based `dxfId`.

- **IR**
  - `ConditionalFormat.dxfStyle`

- **Parsing**
  - Resolved compact font/fill/numberFormat/alignment string; available with semantic format index. Lower-density session rendering can retain this string.


## Source references

- [_parse_conditional_format_element](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L470)
- [_append_conditional_formats](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L187)
- [_conditional_details](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L446)
