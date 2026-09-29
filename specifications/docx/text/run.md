# Text runs

[DOCX](../README.md) / Text runs

An input run can become multiple IR runs around calculated page boundaries.

## Processing

Unknown run children produce `UNSUPPORTED_RUN_CHILD`; unknown paragraph wrappers produce `UNSUPPORTED_PARAGRAPH_CHILD`. `w:footnoteRef`, `w:endnoteRef`, and `w:annotationRef` are ignored as note-internal marks. Adjacent compatible text runs may merge without crossing object, link, revision, or control boundaries.

## Fields

### `text`

- **Output**
  - DTP characters; DTX character data, `<tab/>`, `<br/>`.

- **OOXML**
  - `w:t`, `w:tab`, `w:br`, `w:cr`.

- **IR**
  - `Run.text: str`

- **Parsing**
  - Text is copied after XML decoding; TAB is `\t`, break/carriage return is `\n`. DTX normalizes CRLF/CR to LF before emitting br/tab elements.

### `objects`

- **Output**
  - Inline object elements after this IR run text.

- **OOXML**
  - `w:drawing`, `w:pict`, OMML, references, `w:object`.

- **IR**
  - `Run.objects: list[InlineObject]`

- **Parsing**
  - Collect objects in encountered order; the current serializer emits text before objects within each run segment, even if an object preceded later text in the same XML run.

### `styleId`

- **Output**
  - Internal style identifier.

- **OOXML**
  - `w:rPr/w:rStyle/@w:val`

- **IR**
  - Optional `Run.styleId: str`

- **Parsing**
  - Retained only when character formatting is enabled.

### `format`

- **Output**
  - Semantic wrappers; see [emphasis](emphasis.md).

- **OOXML**
  - Paragraph style, run style, direct `w:rPr`.

- **IR**
  - `Run.format: RunFormat`

- **Parsing**
  - Merge in that order; explicit false/None/empty removes inherited key. Store only visible nonempty keys.

### `pageBreak`

- **Output**
  - Page-boundary marker.

- **OOXML**
  - `w:lastRenderedPageBreak`

- **IR**
  - Optional `bool`

- **Parsing**
  - See [pagination](../document/pagination.md).

### `contentControls`

- **Output**
  - Nested DTX control wrappers.

- **OOXML**
  - Inline `w:sdt`.

- **IR**
  - `list[ContentControl]`

- **Parsing**
  - Parse sdtContent first; append the enclosing control to each child run. Nested inline stacks are therefore assembled from inner to outer.


## Source references

- [RunParser.parse](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/runs.py#L47)
- [RunParser._handle_child](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/body/runs.py#L107)
- [_append_inline](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L102)
- [_append_text_with_breaks](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx_content.py#L106)
