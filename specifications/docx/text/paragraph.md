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

### `styleId`

- **Output**
  - Internal style lookup.

- **OOXML**
  - `w:pPr/w:pStyle/@w:val`

- **IR**
  - `str | None`

- **Parsing**
  - Copy explicit value; resolve properties through style `basedOn`.

- **Absence and defaults**
  - `None`; no style-name/size heuristic.

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


## Source references

- [DocumentBodyParser.parse_paragraph](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/scanner.py#L185)
- [_append_block](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L65)
- [_add_semantic_block_attrs](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L88)
