# Slides

[PPTX](../README.md) / Slides

Slides follow the relationship sequence in ppt/presentation.xml.

## Fields

### `number`

- **Output**
  - `slide/@number`; plain `=== Slide N ===`.

- **OOXML**
  - `p:presentation/p:sldIdLst/p:sldId/@r:id`

- **IR**
  - `SlideBlock.n: int`

- **Parsing**
  - Resolve an internal slide relationship and existing part; parse XML; increment the accepted-slide counter. Invalid XML is skipped. An invalid root or missing shape tree can still yield a counted empty slide.

- **Diagnostics**
  - `PRESENTATION_MISSING_SLDIDLST`, `SLIDE_MISSING_RID`, `SLIDE_REL_UNRESOLVED`, `SLIDE_PART_MISSING`, `SLIDE_XML_INVALID`, `SLIDE_INVALID_ROOT`, `SLIDE_MISSING_SPTREE`.

### `id`

- **Output**
  - Internal slide locator and navigation target.

- **OOXML**
  - Accepted slide ordinal.

- **IR**
  - `SlideBlock.id: str`

- **Parsing**
  - `f"slide{n}"`.

### `type`

- **Output**
  - Internal discriminant.

- **OOXML**
  - Slide traversal.

- **IR**
  - `SlideBlock.type: str`

- **Parsing**
  - Always slide.

### `part`

- **Output**
  - Diagnostic and resource locator.

- **OOXML**
  - Resolved relationship target.

- **IR**
  - `SlideBlock.part: str`

- **Parsing**
  - Canonical package part.

### `sldId`

- **Output**
  - Internal source slide ID.

- **OOXML**
  - `p:sldId/@id`

- **IR**
  - `SlideBlock.sldId: str`

- **Parsing**
  - Copy or empty string; not the generated slide ID.

### `hidden`

- **Output**
  - `slide/@hidden="true"`.

- **OOXML**
  - `p:sld/@show`

- **IR**
  - `SlideBlock.hidden: bool`

- **Parsing**
  - True exactly when show == "0". Hidden slides remain in output.

### `shapes`

- **Output**
  - Slide child content.

- **OOXML**
  - `p:cSld/p:spTree`

- **IR**
  - `list[ShapeBlock]`

- **Parsing**
  - Recursive source order through grpSp; skip group property nodes. Resolve connectors, remove decoration, then renumber. Public plans do not enable geometry sorting.

### `section`

- **Output**
  - `slide/@section`; plain section label.

- **OOXML**
  - Presentation section membership.

- **IR**
  - `str | None`

- **Parsing**
  - See [sections](section.md).

### `notes`

- **Output**
  - `speaker-notes` after shapes.

- **OOXML**
  - Related notes slide.

- **IR**
  - `str | None`

- **Parsing**
  - See [notes](../ancillary/notes.md).

### `commentRefs`

- **Output**
  - `comment-ref` before shapes.

- **OOXML**
  - Attached comments.

- **IR**
  - `list[CommentRef]`

- **Parsing**
  - See [comments](../ancillary/comment.md).

### `background`

- **Output**
  - Semantic background attributes if populated.

- **OOXML**
  - Explicit p:cSld/p:bg.

- **IR**
  - `SlideBackground | None`

- **Parsing**
  - See [background](background.md). Public plans leave it None.


## Source references

- [_SlideSequence](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/runner.py#L126)
- [SlideParser._shapes](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L121)
- [_append_slide](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L26)
