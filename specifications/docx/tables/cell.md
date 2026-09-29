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
  - 0-based; enumeration of direct tr nodes.

### `isHeader`

- **Output**
  - `tr/@header="true"`; child `th` instead of `td`.

- **OOXML**
  - Presence of `w:trPr/w:tblHeader`.

- **IR**
  - `TableRow.isHeader: bool`

- **Parsing**
  - Current parser tests element presence, not the on/off attribute.

- **Absence and defaults**
  - Omitted when no element.

### `cells`

- **Output**
  - DTX th/td sequence.

- **OOXML**
  - Direct `w:tc` children.

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
  - Start 0; advance by each parsed colspan.

### `colSpan`

- **Output**
  - DTX `@colspan`, omitted for 1.

- **OOXML**
  - `w:tcPr/w:gridSpan/@w:val`

- **IR**
  - `TableCell.colSpan: int`

- **Parsing**
  - `max(1, int(value))`.

- **Absence and defaults**
  - 1.

- **Diagnostics**
  - Invalid integer: `INVALID_GRID_SPAN`, locator word/document.xml, fallback 1.

### `rowSpan`

- **Output**
  - DTX `@rowspan`, omitted for 1.

- **OOXML**
  - vMerge continuation sequence.

- **IR**
  - `TableCell.rowSpan: int`

- **Parsing**
  - Start 1. Maintain active origins for covered columns; each continuation increments each distinct origin once. No merge clears active origins for those columns.

### `vMerge`

- **Output**
  - DTX `@v-merge`.

- **OOXML**
  - `w:tcPr/w:vMerge/@w:val`

- **IR**
  - `TableCell.vMerge: str`

- **Parsing**
  - Element without nonempty val → continue; restart creates active origins. Current DTX retains continuation cells rather than suppressing them.

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
  - Recursively parse in source order. Nested headings currently serialize as p, with inline semantics but without their block-level heading/paragraph attributes.


## Source references

- [TableParser._parse_row](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/tables.py#L122)
- [TableParser.apply_vertical_merges](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/tables.py#L197)
- [_append_cell_content](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L222)
