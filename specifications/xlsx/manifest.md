# Parse manifest

[XLSX](README.md) / Parse manifest

`ParseResult.report.manifest` describes parsed content before rendering. One-shot sheet/range selection narrows this scope; a session retains its full-workbook report.

For a default preview using bounded cell materialization, `cellCount` counts only retained cells in that parse, including the complete threshold row. It is not a worksheet-total statistic. Complete selected-sheet compatibility paths and explicit full sessions report the cells they actually retain.

## Fields

### `sheetCount`

- **Output**
  - `report.manifest["sheetCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `worksheet_infos`

- **Parsing**
  - `len(worksheet_infos)`

- **Notes**
  - Parsed worksheets.

### `cellCount`

- **Output**
  - `report.manifest["cellCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `worksheet_infos`

- **Parsing**
  - `sum(len(row) for sheet in worksheet_infos for row in sheet.get("rows", []))`

- **Notes**
  - Parsed cells, including empty cells and merge/spill shadows.

### `tableCount`

- **Output**
  - `report.manifest["tableCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `worksheet_infos`

- **Parsing**
  - `sum(len(sheet.get("tables", [])) for sheet in worksheet_infos)`

- **Notes**
  - Parsed table definitions.

### `imageCount`

- **Output**
  - `report.manifest["imageCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `worksheet_infos`

- **Parsing**
  - `sum(len(sheet.get("images", [])) for sheet in worksheet_infos)`

- **Notes**
  - Drawing image records.

### `chartCount`

- **Output**
  - `report.manifest["chartCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `worksheet_infos`

- **Parsing**
  - `sum(len(sheet.get("charts", [])) for sheet in worksheet_infos)`

- **Notes**
  - Parsed charts.

### `pivotTableCount`

- **Output**
  - `report.manifest["pivotTableCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `worksheet_infos`

- **Parsing**
  - `sum(len(sheet.get("pivot_tables", [])) for sheet in worksheet_infos)`

- **Notes**
  - Parsed pivot tables.
