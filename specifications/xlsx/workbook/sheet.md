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
  - Exact chartsheet URI → chartsheet; all other types → worksheet.
    A chartsheet has no worksheet grid. Read its root/drawing/@r:id, validate
    the owning drawing relationship and use the existing image/chart reader.
    Both XML densities emit chart summaries inside chart-sheet; plain emits
    the chart-sheet boundary and compact object summaries. Complete chart
    values remain available through chart resources.
  - A missing/invalid chart-sheet part or unresolved drawing binding emits
    CHART_SHEET_UNREADABLE and a visible drawing placeholder. An absent grid
    is not fabricated. A chart sheet cannot accept range_spec.

### `state`

- **Output**
  - sheet/@visibility when not visible; plain hidden/veryHidden label.

- **OOXML**
  - sheet/@state.

- **IR**
  - `SheetInfo.state: str`

- **Parsing**
  - Default visible. Retain every sheet regardless of visibility. Both
    worksheet and chart-sheet output retain non-default visibility.

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
  - Semantic `<sheet-protection/>` only for enabled saved cell-sheet protection.
    Plain/structural omit this marker and cell protection attributes.

- **OOXML**
  - s:sheetProtection/@sheet.

- **IR**
  - `bool`

- **Parsing**
  - 1/true enables protection. 0/false, absent @sheet or an absent element
    disables it. An invalid boolean emits RULE_BOOLEAN_INVALID and uses false.
    The presence of other flags or password settings alone does not enable
    cell-sheet protection.
  - [Cell protection](../styles/style.md#locked) describes saved cell flags.
    Passwords, allowed-edit exceptions and application permissions are not
    enforced. Sheet/row/column visibility has its own independent contract.
