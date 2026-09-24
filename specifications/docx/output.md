# Output profile

[DOCX](README.md) / Output profile

DOCX output uses the common [DTX](../common/dtx.md) and [DTP](../common/dtp.md) serialization rules.

## Synopsis

```xml
<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final" schema="doctokens-xml" version="1.0"><body><page number="1"/><p>Hello <b>world</b>.</p></body></document>
```

## Processing

Plain separates retained blocks with blank lines; table summaries, note/comment labels, and object summaries are readable content. Only the DTP header and escaped page markers have the common DTP syntax. Empty XML body emits page 1.

## Fields

### `format`

- **Output**
  - `document/@format="docx"`; DTP header format=docx.

- **OOXML**
  - Public format selection.

- **IR**
  - Constant.

- **Parsing**
  - Use docx.

### `pagination`

- **Output**
  - `document/@pagination="last-rendered-hints"`; same DTP header value.

- **OOXML**
  - Saved pagination markers.

- **IR**
  - Constant description of page numbering.

- **Parsing**
  - See [pagination](document/pagination.md).

### `revision-view`

- **Output**
  - DTX root attribute; DTP revision_view header.

- **OOXML**
  - ParseOptions.revision_mode.

- **IR**
  - `metadata["revisionView"]`

- **Parsing**
  - Use selected final/original/review value.

### `body`

- **Output**
  - First document child.

- **OOXML**
  - Body IR.

- **IR**
  - `ParsedDocument.blocks`

- **Parsing**
  - Emit pages, optional sections, and block content in source order.

### `assets`

- **Output**
  - Optional child following body.

- **OOXML**
  - Image relationship index.

- **IR**
  - `ParsedDocument.assets`

- **Parsing**
  - Emit every indexed image; semantic adds external href. This inventory can include assets not referenced by selected body blocks.

### `supplemental`

- **Output**
  - Optional child after assets.

- **OOXML**
  - Ancillary IR.

- **IR**
  - headers/footers/footnotes/endnotes/comments.

- **Parsing**
  - Semantic order: headers, footers, footnotes, endnotes, comments. Structural: footnotes, endnotes, comments. Omit empty groups.


## Source references

- [iter_dtx](../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L29)
- [iter_plain](../../packages/docx_llm_parser/src/docx_llm_parser/rendering/document/pipeline.py#L16)
