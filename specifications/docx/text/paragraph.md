# Paragraphs

[DOCX](../README.md) / Paragraphs

A visible paragraph becomes one paragraph block before page-window projection.

## Fields

### `text`

- **Output**
  - Plain paragraph text; DTX character-data fallback.

- **OOXML**
  - Parsed `w:r` text and synthetic numbering run.

- **IR**
  - `ParagraphBlock.text: str`

- **Parsing**
  - `"".join(run["text"] for run in runs)`; objects are stored separately. Discard whitespace-only paragraphs unless objects, controls, or `preserve_empty_paragraphs` require retaining them.
  - Project tracked paragraph marks before extraction. Adjacent source paragraphs whose intervening mark is removed become one reading paragraph; preserve their text and inline content order without adding a separator. See [revisions](revision.md).

### `styleId`

- **Output**
  - Internal style lookup.

- **OOXML**
  - `w:pPr/w:pStyle/@w:val`

- **IR**
  - `str | None`

- **Parsing**
  - Use the selected current/historical pPr and a valid paragraph style reference; otherwise select the document's default paragraph style. Resolve document defaults, table context, and the style basedOn chain before direct paragraph properties.

- **Absence and defaults**
  - Default paragraph style ID, or None if none is defined. No style-name/size heuristic.

### `runs`

- **Output**
  - DTX inline sequence.

- **OOXML**
  - Paragraph inline descendants.

- **IR**
  - `ParagraphBlock.runs: list[Run]`

- **Parsing**
  - Retain when `include_runs=True`; see [runs](run.md).

- **Absence and defaults**
  - Without runs, DTX uses text; object/format detail can therefore be unavailable.

### `align`

- **Output**
  - Semantic `p|hN/@align`.

- **OOXML**
  - `w:pPr/w:jc/@w:val`, then style alignment.

- **IR**
  - `ParagraphBlock.alignment: str`

- **Parsing**
  - Lowercase explicit value; direct nonempty value wins. Renderer accepts `center`, `right`, `distribute`.

- **Absence and defaults**
  - Left alignment and unrecognized values produce no attribute.

### `numbering`

- **Output**
  - Semantic `numbering="true"`; visible prefix in every density.

- **OOXML**
  - `w:numPr` and numbering/style definitions.

- **IR**
  - `ParagraphBlock.numbering: NumberingLabel`

- **Parsing**
  - Insert marker as first synthetic run; see [numbering](numbering.md).

- **Absence and defaults**
  - No label record: omit attribute.

### `contentControls`

- **Output**
  - DTX nested `content-control` wrappers.

- **OOXML**
  - Enclosing block `w:sdt`.

- **IR**
  - `list[ContentControl]`

- **Parsing**
  - Propagate enclosing control stack; parse content at its original position. See [controls](control.md).

### `rawHints`

- **Output**
  - No main-text projection.

- **OOXML**
  - Run/drawing/field diagnostics.

- **IR**
  - `list[RawHint]`

- **Parsing**
  - Retain only with RAW_HINTS plan, `include_raw_hints=True`, and nonempty collected hints.
