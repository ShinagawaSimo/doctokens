# Parse manifest

[DOCX](README.md) / Parse manifest

`ParseResult.report.manifest` describes parsed content before rendering. Page/slide selection does not recalculate these counts.

## Fields

### `pageCount`

- **Output**
  - `report.manifest["pageCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_document`

- **Parsing**
  - `max((block.get("page", 1) for block in parsed_document.blocks), default=1)`

- **Notes**
  - Maximum starting content page among top-level blocks; does not inspect `pageEnd`.

### `blockCount`

- **Output**
  - `report.manifest["blockCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_document`

- **Parsing**
  - `len(parsed_document.blocks)`

- **Notes**
  - Top-level blocks only.

### `tableCount`

- **Output**
  - `report.manifest["tableCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_document`

- **Parsing**
  - `sum(1 for block in parsed_document.blocks if block["type"] == "table")`

- **Notes**
  - Counts page-split table segments separately; excludes nested tables.

### `imageCount`

- **Output**
  - `report.manifest["imageCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_document`

- **Parsing**
  - `len(parsed_document.assets)`

- **Notes**
  - Parsed asset records.

### `chartCount`

- **Output**
  - `report.manifest["chartCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_document`

- **Parsing**
  - `len(parsed_document.charts)`

- **Notes**
  - Parsed chart records.

### `smartartCount`

- **Output**
  - `report.manifest["smartartCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_document`

- **Parsing**
  - `len(parsed_document.smartarts)`

- **Notes**
  - Parsed SmartArt records.

### `commentCount`

- **Output**
  - `report.manifest["commentCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_document`

- **Parsing**
  - `len(parsed_document.comments)`

- **Notes**
  - Parsed comments.


## Source references

- [DocxParser.parse](../../packages/docx_llm_parser/src/docx_llm_parser/parsing/runner.py#L43)
