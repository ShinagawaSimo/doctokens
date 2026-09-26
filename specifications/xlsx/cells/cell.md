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
  - inlineStr → direct is/t only; s → shared-string lookup; b → true exactly for v="1", otherwise false; other types → v text. Missing/empty v → empty string. Invalid shared index → empty string without warning. Numeric t=n with nonempty text and s attribute uses display formatting.

- **Absence and defaults**
  - Empty string.

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

- [_parse_cell](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L578)
- [_cell_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L635)
- [SheetWorkingSet.finalize](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L176)
- [_cell_attrs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L339)
- [parse_ref](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_utils.py#L9)
