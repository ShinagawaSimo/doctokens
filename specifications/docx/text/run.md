# Text runs

[DOCX](../README.md) / Text runs

[Alternate content](../document/alternate-content.md) is resolved before run
dispatch. Only the selected branch's children reach the ordinary run handlers.

An input run can become multiple IR runs around calculated page boundaries.

## Processing

Unknown run children produce `UNSUPPORTED_RUN_CHILD`; unknown paragraph wrappers produce `UNSUPPORTED_PARAGRAPH_CHILD`. `w:footnoteRef`, `w:endnoteRef`, and `w:annotationRef` are ignored as note-internal marks. Adjacent compatible text fragments may merge without crossing object, ruby, link, revision, author/date, or control boundaries.

## Fields

### `text`

- **Output**
  - DTP characters; DTX character data, `<tab/>`, `<br/>`.

- **OOXML**
  - `w:t`, selected deletion/move-source `w:delText`, `w:tab`, `w:br`, `w:cr`, `w:noBreakHyphen`, `w:softHyphen`, `w:sym`, and ruby base text.

- **IR**
  - `Run.text: str`

- **Parsing**
  - Text is copied after XML decoding; TAB is `\t`, break/carriage return is `\n`. DTX normalizes CRLF/CR to LF before emitting br/tab elements.
  - `noBreakHyphen` is U+2011: `A`, `noBreakHyphen`, `B` produces `A‑B`. `softHyphen` is a discretionary line-layout glyph and contributes no visible character to unbroken reading text.
  - Decode a four-digit hexadecimal `sym/@w:char` using its explicit `@w:font`. Known Symbol byte/U+F000-prefixed codes use the shared [encoding map](../../../packages/doctokens_core/src/doctokens_core/ooxml/symbols.py); `Symbol/F061` becomes `α`. Do not assume that a private-use code in another font has the same meaning.
  - Unknown font/glyph mappings produce `�` and `SYMBOL_UNSUPPORTED`; malformed codes produce `�` and `INVALID_SYMBOL_CODE`. Diagnostics identify the part/block. No host font lookup or glyph guessing is performed.

### `objects`

- **Output**
  - Inline object elements after this IR run text.

- **OOXML**
  - `w:drawing`, `w:pict`, OMML, references, `w:object`.

- **IR**
  - `Run.objects: list[InlineObject]`

- **Parsing**
  - Append separate fragments at text/object boundaries. Preserve source order even when a single XML run contains text, an object, and more text. Selected deleted/moved content follows the same path as ordinary content.

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
  - Document defaults, table/paragraph/character style levels, and the selected current/historical direct `w:rPr`.

- **IR**
  - `Run.format: RunFormat`

- **Parsing**
  - Apply the [style cascade](style.md), including toggle rules across independently resolved levels. Retain explicit clear values until final visible projection. Store only visible nonempty keys. Ruby base runs inherit their containing run's effective format before their own overrides. Semantic review can wrap changed formats as defined in [revisions](revision.md).

### `ruby`

- **Output**
  - Semantic `<ruby annotation="han">汉</ruby>`, retaining formatted base content. Structural/plain emit only the base reading text, without repeating the annotation.
- **OOXML**
  - `w:r/w:ruby/w:rubyBase` supplies base runs; sibling `w:rt` supplies the saved guide text.
- **IR**
  - `Run.text` contains the base reading text; `Run.ruby` contains `annotation: str` and `baseRuns: list[Run]`.
- **Parsing**
  - Read base runs through ordinary inline dispatch, including their formats, fields and selected revisions. Keep ruby boundaries even when adjacent base text is identical. A field in the base uses local field-result offsets; an enclosing field applies to the resulting ruby run.
  - Collect guide text in the selected revision view. Guide font size, alignment, raise and other geometry are omitted; guide text is not concatenated into the paragraph or indexed as another occurrence of the base text.
- **Absence and defaults**
  - Empty/missing annotation: render the base content without a ruby wrapper. Missing base container: no reading text.
- **Diagnostics**
  - `RUBY_BASE_MISSING` for a missing base container. `RUBY_NESTING_LIMIT` stops base recursion beyond 32 annotations. Both retain the owning part/block locator.

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
