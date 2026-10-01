# Cells

[XLSX](../README.md) / Cells

Cells retain stored values; formulas are parsed separately and are not calculated.

## Processing

Post-processing order is shared-formula expansion, merged cells, spills, hyperlinks, comments. Full-sheet parsing may create cells for hyperlinks/comments, then sorts rows and cells by coordinates. Merge/spill processing does not create cells.

## Fields

### `ref`

- **Output**
  - Internal A1 identity; comment/@cell and selection locators.

- **OOXML**
  - s:c/@r.

- **IR**
  - `Cell.ref: str`

- **Parsing**
  - Copy explicit reference; missing → next column after previous parsed source cell and effective row. Coordinates parsed with parse_ref.

### `row`

- **Output**
  - Containing tr number.

- **OOXML**
  - Effective row/@r, fallback reference row.

- **IR**
  - `Cell.row: int`

- **Parsing**
  - Use effective enclosing row when nonzero, even if the explicit reference contains a different row.

### `col`

- **Output**
  - cell/@column only when needed for a gap.

- **OOXML**
  - A1 column in ref.

- **IR**
  - `Cell.col: int`

- **Parsing**
  - 1-based column; renderer emits its letter if different from expected_col. Expected starts at grid minimum and advances by each emitted cell's colspan. A suppressed shadow cell does not advance it.

### `text`

- **Output**
  - cell text or inline content.

- **OOXML**
  - s:c/@t; s:v; s:is/s:t.

- **IR**
  - `Cell.text: str`

- **Parsing**
  - inlineStr → direct is/t only; s → shared-string lookup; b → `TRUE` exactly for v="1", otherwise `FALSE`, matching Excel's displayed logical values; other types → v text. Missing/empty v → empty string. Invalid shared index → empty string without warning. Numeric t=n with nonempty text and s attribute uses display formatting. Formula caches with t=b follow the same logical-value rule.

- **Absence and defaults**
  - Empty string.

### `raw`

- **Output**
  - Structural and semantic DTX emit `cell/@raw` only when a non-formula cell's formula-bar value can be reconstructed reliably and differs from the displayed cell text. Plain output never emits this attribute.

- **OOXML**
  - Shared strings and inline strings provide decoded text. Numeric cells provide a stored value and style; the formula-bar value is an application rendering and is not stored as a separate OOXML field.

- **IR**
  - `Cell.raw: str`

- **Parsing**
  - For text cells, decode shared-string or inline-string content and apply a supported text section around it. For ordinary numeric formats whose edit form is independently recoverable, preserve that formula-bar form. A scientific display token is formatting syntax; the saved ordinary number may be emitted as `raw` when the supported precision and range limits make it reliable. Do not reconstruct `raw` from the rounded scientific display, and do not use a date/time serial, percentage display, or formula cache as `raw`. Formula cells use `formula` and omit `raw`; when a numeric formula-bar value cannot be reconstructed reliably, omit `raw` and add `XLSX_FORMULA_BAR_UNAVAILABLE` to the parse report.
  - Supported Simplified Chinese `DBNum1/2` General integers retain their ordinary numeric edit form. Supported `zh-CN` pure times reconstruct `h:mm:ss` without fractional seconds, independently of the rounded cell display; for example, `raw="12:30:00"` accompanies `12:30:00.1`. This edit-form value is not a lossless encoding of the saved time. See [number formats](../styles/number-format.md#raw) for the precise locale, pattern, and range limits.

- **Absence and defaults**
  - Omit for formula cells and for numeric values whose formula-bar form is uncertain. Omit from DTX when `raw == text`.

### `type`

- **Output**
  - Internal semantic type; no general cell/@type.

- **OOXML**
  - s:c/@t.

- **IR**
  - `Cell.type: str`

- **Parsing**
  - s/inlineStr/str → string; b → boolean; e → error; d → date. Numeric/default n omits type. Rich values with imagePart/imageUrl override to image.

### `style`

- **Output**
  - Input to formatting/protection/control resolution.

- **OOXML**
  - s:c/@s.

- **IR**
  - `Cell.style: int`

- **Parsing**
  - Parse integer, omit invalid. Retained when style-index or semantic-style extraction enabled.

### `rich`

- **Output**
  - Semantic run content.

- **OOXML**
  - Shared string rich runs.

- **IR**
  - `list[RichTextRun]`

- **Parsing**
  - Attach only for t=s and a catalog entry with formatting; see [rich text](rich-text.md).

### `richValue`

- **Output**
  - Rich descriptor and display.

- **OOXML**
  - s:c/@vm.

- **IR**
  - `RichCellValue`

- **Parsing**
  - See [rich values](rich-value.md).
- **Diagnostics**
  - A used `@vm` with no `xl/metadata.xml` yields `XLSX_CATALOG_PART_MISSING`; malformed optional rich metadata or an unusable binding follows [catalog diagnostics](../workbook/catalog-diagnostics.md).

### `cellControl`

- **Output**
  - Control metadata.

- **OOXML**
  - Cell style → feature bags.

- **IR**
  - `CellControl`

- **Parsing**
  - See [controls](control.md).


## Source references

- [_parse_cell](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/cells.py#L42)
- [_cell_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/cells.py#L156)
- [SheetWorkingSet.finalize](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L125)
- [_cell_attrs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L156)
- [parse_ref](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_utils.py#L9)
