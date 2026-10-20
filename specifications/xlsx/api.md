# Parsing and selection

[XLSX](README.md) / Parsing and selection

parse_xlsx/open_xlsx use [common sessions](../common/session.md) and return [ParseResult](../common/result.md).

## Processing

One-shot explicit ranges narrow cell materialization while retaining minimal shared-formula master declarations from the same worksheet when formulas are requested. Default sheet/workbook previews still parse the selected sheets before rendering a bounded cell window; an output threshold does not promise streaming parsing or bounded memory. Session rendering selects from an already parsed workbook. Window parsing does not create missing annotation cells. The resource directory reflects the parsed scope, not only emitted grid rows.

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
  - Exact case-sensitive display-name match; missing name → KeyError. None selects all sheets in the parser API, with a separate default cell window for each. The MCP tool selects the first worksheet by default and reads only one sheet per call.

### `range_spec`

- **Output**
  - Selected sparse cell range.

- **Source**
  - Call argument.

- **IR**
  - `str | None = None`

- **Parsing**
  - Requires sheet. Accept `A1:H20` rectangles, `10:20` whole rows, and single `A1` cells (also `A1:A1`). Cell references accept upper/lowercase columns and optional `$` markers. Rows and columns are one-based and endpoints inclusive; require ascending bounds within A1:XFD1048576. Reject reversed, zero, malformed, qualified/multiple-sheet or out-of-range coordinates with ValueError. Whole-row ranges use columns A:XFD without blank filling. Chartsheets reject cell ranges.
  - An explicit range includes all saved selected cells without the default 500-cell threshold. Omitted ranges use a [reading window](reading-window.md) in all densities, finishing the row that reaches 500 emitted cells. A selected sheet alone is a preview, not an unlimited full-sheet request.
  - In structural and semantic output, shared-formula dependents inside the range can resolve a master outside it; that master does not enter the selected grid. See [shared formulas](cells/shared-formula.md).
  - A merge crossing the requested boundary does not expand the selection. `selection.windows[].merged_ranges` identifies the saved merge range, anchor and whether that anchor lies within the request, even if no saved cells occur inside the requested portion.

### `options`

- **Output**
  - Package limits and diagnostic options.

- **Source**
  - ParseOptions.

- **IR**
  - `ParseOptions | None`

- **Parsing**
  - See [package options](../common/package.md). No XLSX OCR option.


### `inspect_xlsx(source, options=...)`

- **Output**
  - JSON-compatible `format`, `scope="workbook-index"`, `sheet_count`, `sheets`, `date_1904`, `defined_names`, and `external_links`.
  - Each sheet exposes `name`, `kind`, and `visibility` (default `visible`).

- **Parsing**
  - Reuses workbook metadata and relationship reading with the same package limits. Opens and closes its own package reader; does not load worksheets, shared strings, styles, or cell data.
  - Cell and resource counts are not inferred. Normal parse/session entry points retain their existing default body behavior.
