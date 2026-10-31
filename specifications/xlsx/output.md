# Output profile

[XLSX](README.md) / Output profile

XLSX uses [DTX](../common/dtx.md) and [DTP](../common/dtp.md).

## Processing

Plain whole-workbook output uses `<sheet name=...>` / `<chartsheet name=...>` readable labels, metadata summaries, and TAB-separated parsed cells. It is not an XML document. Selected plain output consists of the DTP header and selected rows, followed by `[Truncated: next row N]` when a default preview withholds rows. Exact explicit ranges have no preview cutoff. See [reading windows](reading-window.md).

Plain table summaries contain only the saved table name and source range, for
example `[Table Orders A1:C3]`; declared column names are not repeated before
the grid. `[Filter A1:C3]` is emitted only when saved conditions exist. It does
not certify that the parser applied a filter. A filter button without saved
conditions adds no plain marker. Slicer/timeline name directories without
readable selection state are omitted from plain; their supported metadata
remains available in XML workbook output.

## Fields

### `format`

- **Output**
  - workbook/@format=xlsx; DTP format=xlsx.

- **OOXML**
  - Public parser.

- **IR**
  - Constant.

- **Parsing**
  - xlsx.

### `metadata`

- **Output**
  - Root metadata before sheets.

- **OOXML**
  - WorkbookMetadata.

- **IR**
  - defined_names/external_links/pivot_caches/slicers/timelines.

- **Parsing**
  - Full DTX order: global names, external links, pivot caches, slicers, timelines,
    sheets. A selected sheet retains its existing sheet-level index. An explicit
    range emits only relevant names and external/pivot dependencies at root.
    Scoped range-context names carry @sheet and appear once, including a hidden
    name when a retained expression explicitly needs it.

### `sheet content`

- **Output**
  - Sheet metadata then grid.

- **OOXML**
  - SheetInfo.

- **IR**
  - Sheet collections.

- **Parsing**
  - Order: hidden columns, protection, local names, filter, validation,
    conditional formatting, images, charts, drawings, pivots, tables, grid.
    Exact ranges restrict context by the requested bounds, even when the
    selected grid is empty. See [reading windows](reading-window.md#range-context).
