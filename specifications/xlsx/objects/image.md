# Drawing images

[XLSX](../README.md) / Drawing images

Images are referenced by package location without eager binary reads.

## Fields

### `id`

- **Output**
  - img/@id.

- **OOXML**
  - First resolvable a:blip/@r:embed per anchor.

- **IR**
  - `DrawingImage.id: str`

- **Parsing**
  - image1,image2,... across accepted sheet objects. r:link is not used.

### `ref`

- **Output**
  - img/@ref.

- **OOXML**
  - Drawing start anchor.

- **IR**
  - `str`

- **Parsing**
  - See [anchors](drawing.md).

### `alt`

- **Output**
  - Internal empty string; no DTX alt.

- **OOXML**
  - No alternative-text extraction on this path.

- **IR**
  - `str`

- **Parsing**
  - Assigned empty string.

### `part`

- **Output**
  - Resource package part.

- **OOXML**
  - Resolved blip relationship target.

- **IR**
  - `str`

- **Parsing**
  - Require nonempty target to index; target existence/type is not validated in _parse_drawing_anchor. Resource descriptor source is embedded; unreadable targets fail when read_resource opens them.


## Source references

- [_parse_drawing_anchor](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/drawings.py#L91)
- [_resource_descriptors](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/_resources.py#L12)
