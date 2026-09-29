# Sheets

[XLSX](../README.md) / Sheets

Sheet order is the workbook sheet-list order.

## Fields

### `name`

- **Output**
  - sheet/@name; chart-sheet/@name.

- **OOXML**
  - xl/workbook.xml/s:workbook/s:sheets/s:sheet/@name.

- **IR**
  - `SheetInfo.name: str`

- **Parsing**
  - Copy; default empty string.

### `part`

- **Output**
  - Internal part locator.

- **OOXML**
  - sheet/@r:id → workbook relationship.

- **IR**
  - `SheetInfo.part: str`

- **Parsing**
  - Resolved target; missing/unresolved relation falls back to xl/worksheets/sheetN.xml, N=1-based sheet-list position. Missing worksheet part then raises PackageError.

### `kind`

- **Output**
  - sheet or chart-sheet element.

- **OOXML**
  - Relationship type.

- **IR**
  - `SheetInfo.kind: str`

- **Parsing**
  - Exact chartsheet URI → chartsheet; all other types → worksheet. Chartsheets emit name only and skip worksheet/drawing extraction.

### `state`

- **Output**
  - sheet/@visibility when not visible; plain hidden/veryHidden label.

- **OOXML**
  - sheet/@state.

- **IR**
  - `SheetInfo.state: str`

- **Parsing**
  - Default visible. Retain every sheet regardless of visibility. Chartsheet output omits visibility.

### `rows`

- **Output**
  - Sheet grid.

- **OOXML**
  - Worksheet sheetData/row/c.

- **IR**
  - `list[list[Cell]]`

- **Parsing**
  - See [rows](../cells/row.md), [cells](../cells/cell.md), [grid](../cells/grid.md).

### `hidden_cols`

- **Output**
  - `<columns ref="B:D" hidden="true"/>`.

- **OOXML**
  - s:cols/s:col[@hidden="1"]/@min,@max.

- **IR**
  - `list[tuple[int,int]]`

- **Parsing**
  - 1-based inclusive ranges. Plain omits cells whose column is covered; XML retains them.

### `sheet_protection`

- **Output**
  - `<sheet-protection/>`.

- **OOXML**
  - Presence of s:sheetProtection.

- **IR**
  - `bool`

- **Parsing**
  - Element presence determines true; protection flags/password are not enforced.


## Source references

- [_parse_workbook_xml](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/workbook/metadata.py#L32)
- [SheetPostIndex](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L46)
- [_append_sheet](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L43)
