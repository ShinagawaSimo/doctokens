# Output profile

[XLSX](README.md) / Output profile

XLSX uses [DTX](../common/dtx.md) and [DTP](../common/dtp.md).

## Processing

Plain whole-workbook output uses `<sheet name=...>` / `<chartsheet name=...>` readable labels, metadata summaries, and TAB-separated parsed cells. It is not an XML document. Selected plain output consists of the DTP header and selected rows only.

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
  - Full DTX order: global names, external links, pivot caches, slicers, timelines, sheets. Selected-sheet/range output does not append these root records.

### `sheet content`

- **Output**
  - Sheet metadata then grid.

- **OOXML**
  - SheetInfo.

- **IR**
  - Sheet collections.

- **Parsing**
  - Order: hidden columns, protection, local names, filter, validation, conditional formatting, images, charts, pivots, tables, grid. Range output keeps this sheet metadata even when objects lie outside selected cells.


## Source references

- [iter_dtx](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L19)
- [render_sheet_dtx](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L28)
- [iter_plain](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/plain.py#L12)
- [_render_selected_plain](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py#L371)
