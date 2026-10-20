# Cell hyperlinks

[XLSX](../README.md) / Cell hyperlinks

A hyperlink is attached to its source reference without evaluating it.

## Fields

### `hyperlink`

- **Output**
  - `cell/a/@href`.

- **OOXML**
  - s:hyperlinks/s:hyperlink/@ref,@r:id,@location.

- **IR**
  - `Cell.hyperlink: str`

- **Parsing**
  - Resolved relation target wins; append #location when nonempty. Without target, use #location. Neither → no link. Full-sheet parsing can create a blank target cell; a parse window only annotates existing selected cells. No missing-target warning.
