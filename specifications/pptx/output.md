# Output profile

[PPTX](README.md) / Output profile

PPTX uses [DTX](../common/dtx.md) or [DTP](../common/dtp.md).

## Processing

Plain labels each slide `=== Slide N ===`, with section suffix if present; separates visible shapes by blank lines. Notes follow shapes. XML uses `p`/`title` for a single paragraph and `textbox` with child paragraphs for a multi-paragraph text object; title containers use `role="title"`. The public XML format contains no shape coordinates.

Both XML densities retain a slide-local `shape-id` for each primary source
shape. Connector endpoints reference that field. Resource `id` values remain
separate, so a picture/chart/SmartArt can be addressed both as a slide object
and as a reusable resource. See [shapes](shapes/shape.md).

## Fields

### `format`

- **Output**
  - presentation/@format=pptx; DTP format=pptx.

- **OOXML**
  - Public parser.

- **IR**
  - Constant.

- **Parsing**
  - pptx.

### `slides`

- **Output**
  - presentation/slide children.

- **OOXML**
  - Parsed slide sequence.

- **IR**
  - `ParsedPresentation.slides`

- **Parsing**
  - Original accepted-slide order; hidden slides included.

### `comments`

- **Output**
  - presentation/comments after slides.

- **OOXML**
  - Parsed comment records.

- **IR**
  - `ParsedPresentation.comments`

- **Parsing**
  - Both XML densities; plain appends [Comments] with [cmtN: text].
