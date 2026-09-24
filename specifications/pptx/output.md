# Output profile

[PPTX](README.md) / Output profile

PPTX uses [DTX](../common/dtx.md) or [DTP](../common/dtp.md).

## Processing

Plain labels each slide `=== Slide N ===`, with section suffix if present; separates visible shapes by blank lines. Notes follow shapes. XML text shape tags derive only from placeholder type. The public XML format contains no shape coordinates.

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


## Source references

- [iter_dtx](../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L16)
- [iter_plain](../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/plain.py#L13)
