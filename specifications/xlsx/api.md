# Parsing and selection

[XLSX](README.md) / Parsing and selection

parse_xlsx/open_xlsx use [common sessions](../common/session.md) and return [ParseResult](../common/result.md).

## Processing

One-shot sheet/range selection narrows parsing. A shared-formula master outside a selected range is therefore unavailable for slave expansion; a session parses all sheets first. Window parsing does not create missing annotation cells. The resource directory reflects the parsed scope, not only emitted grid rows.

## Fields

### `source`

- **Output**
  - Input package.

- **Source**
  - XLSX OPC package.

- **IR**
  - `str | Path | bytes`

- **Parsing**
  - Path or complete ZIP bytes.

### `density`

- **Output**
  - DTP/DTX projection.

- **Source**
  - Call argument.

- **IR**
  - `str = "structural"`

- **Parsing**
  - plain/structural/semantic only; invalid → ValueError.

### `sheet`

- **Output**
  - Selected sheet.

- **Source**
  - Call argument.

- **IR**
  - `str | None = None`

- **Parsing**
  - Exact case-sensitive display-name match; missing name → KeyError. None selects all.

### `range_spec`

- **Output**
  - Selected sparse cell range.

- **Source**
  - Call argument.

- **IR**
  - `str | None = None`

- **Parsing**
  - Requires sheet. Must contain colon and two parseable A1 references; single cell can be written A1:A1. Keep cells whose coordinates are inside inclusive bounds; no blank filling. Reversed bounds are not normalized.

### `options`

- **Output**
  - Package limits and diagnostic options.

- **Source**
  - ParseOptions.

- **IR**
  - `ParseOptions | None`

- **Parsing**
  - See [package options](../common/package.md). No XLSX OCR option.


## Source references

- [parse_xlsx](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py#L333)
- [parse_range](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/selection.py#L17)
- [filter_rows](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/selection.py#L27)
