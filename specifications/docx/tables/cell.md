# Rows and cells

[DOCX](../README.md) / Rows and cells

Rows and cells use table-local coordinates.

## Fields

### `rowIndex`

- **Output**
  - Internal index.

- **OOXML**
  - Position of `w:tr`.

- **IR**
  - `TableRow.rowIndex`, `TableCell.rowIndex: int`

- **Parsing**
  - 0-based within the selected-view rows, after expanding wrappers and filtering structural revisions.

### `isHeader`

- **Output**
  - `tr/@header="true"`; child `th` instead of `td`.

- **OOXML**
  - `w:trPr/w:tblHeader`, selected from saved history in original view.

- **IR**
  - `TableRow.isHeader: bool`

- **Parsing**
  - Honor the OOXML on/off value, including an explicit false.

- **Absence and defaults**
  - Omitted when no element.

### `cells`

- **Output**
  - DTX th/td sequence.

- **OOXML**
  - `w:tc` children, including wrapped cells.

- **IR**
  - `TableRow.cells: list[TableCell]`

- **Parsing**
  - Preserve source order.

### `colIndex`

- **Output**
  - Internal starting grid column.

- **OOXML**
  - Preceding tc gridSpan values.

- **IR**
  - `TableCell.colIndex: int`

- **Parsing**
  - Start at row gridBefore; advance by each retained cell's gridSpan. gridAfter contributes trailing omitted positions. Cell insertion/deletion is selected before assigning coordinates.

### `colSpan`

- **Output**
  - DTX `@colspan`, omitted for 1.

- **OOXML**
  - `w:tcPr/w:gridSpan/@w:val`

- **IR**
  - `TableCell.colSpan: int`

- **Parsing**
  - Positive integer from the selected property set; nonpositive/invalid values warn and fall back to 1.

- **Absence and defaults**
  - 1.

- **Diagnostics**
  - `INVALID_GRID_SPAN`, owning-part locator, fallback 1.

### `rowSpan`

- **Output**
  - DTX `@rowspan`, omitted for 1.

- **OOXML**
  - vMerge continuation sequence.

- **IR**
  - `TableCell.rowSpan: int`

- **Parsing**
  - Start 1. Maintain active origins for covered columns; each continuation increments each distinct origin once across page segments. A nonmerged cell or omitted grid position clears active origins at those columns.

### `vMerge`

- **Output**
  - DTX `@v-merge`.

- **OOXML**
  - `w:tcPr/w:vMerge/@w:val`

- **IR**
  - `TableCell.vMerge: str`

- **Parsing**
  - Element without nonempty val → continue; restart creates active origins. DTX retains continuation cells. A tracked cellMerge selects vMergeOrig for original and vMerge for final/review, mapping cont/rest to continue/restart.

- **Absence and defaults**
  - No element: absent.

### `text`

- **Output**
  - Plain cell text; DTX fallback.

- **OOXML**
  - Nested parsed blocks.

- **IR**
  - `TableCell.text: str`

- **Parsing**
  - Paragraph text joined with LF; nested-table row cells joined with ` | ` in this summary.

### `blocks`

- **Output**
  - DTX p, page milestones, inline objects, nested-table.

- **OOXML**
  - Cell p/tbl/sdt children.

- **IR**
  - `TableCell.blocks: list[Block]`

- **Parsing**
  - Recursively parse in source order. Paragraph-mark projection, headings, alignment, borders, and review metadata use the same rules as the body.

### `gridBefore` and `gridAfter`

- **Output**
  - Row `@grid-before` / `@grid-after` when nonzero; corresponding empty slots in plain text.
- **OOXML**
  - Selected `w:trPr/w:gridBefore|w:gridAfter/@w:val`.
- **IR**
  - Optional nonnegative `TableRow.gridBefore` / `gridAfter`.
- **Diagnostics**
  - Invalid/negative values report `INVALID_TABLE_GRID_OFFSET` and use zero. Excessive total width raises ValueError according to max_table_columns.

### `contentControls`

- **Output**
  - Existing content-control wrappers around rows/cells in DTX and table resources; compact control marks in plain.
- **OOXML**
  - Row-level and cell-level w:sdt wrappers.
- **IR**
  - `TableRow.contentControls`, `TableCell.contentControls`.
- **Parsing**
  - Keep the control at its structural level, separately from controls inside cell paragraphs. Preserve nested tables and merge positions.

### `background`

- **Output**
  - Semantic cell `@background`, including full table resource output.
- **OOXML**
  - Table-style/conditional tcPr/shd, table defaults and row exceptions, then direct selected cell shd.
- **IR**
  - Optional `TableCell.background` literal color.
- **Parsing**
  - Resolve inheritance and explicit cancellation before output. Theme-only colors do not imply full theme resolution.
