# SmartArt

[PPTX](../README.md) / SmartArt

The diagram extractor uses its own node and connection conventions.

## Fields

### `id`

- **Output**
  - smartart/@id.

- **OOXML**
  - diagramData relationship ordinal.

- **IR**
  - `SmartArtRecord.id` → `ShapeBlock.smartartId`

- **Parsing**
  - smartart1...; lazy-load referenced part.

- **Diagnostics**
  - SMARTART_MISSING_RELIDS, SMARTART_MISSING_DM, SMARTART_ASSET_MISSING, SMARTART_PART_MISSING, SMARTART_PARSE_ERROR.

### `part`

- **Output**
  - Resource locator.

- **OOXML**
  - Resolved diagramData target.

- **IR**
  - `SmartArtRecord.part: str`

- **Parsing**
  - Copy package path.

### `layoutType`

- **Output**
  - smartart/@type.

- **OOXML**
  - Related diagramLayout first nonempty cat/@type.

- **IR**
  - `SmartArtRecord.layoutType`, `ShapeBlock.layoutType`

- **Parsing**
  - Take text after final slash. Shape lookup uses relIds/@r:lo; resource fallback uses first category associated with source part.

### `nodes`

- **Output**
  - Space-joined DTX text; resource nodes.

- **OOXML**
  - Descendants with local name pt.

- **IR**
  - `list[SmartArtNode]`

- **Parsing**
  - Keep every pt, including empty labels; node id is 1-based position; text concatenates descendant local-name t without stripping. Plain outputs type/count only.

### `nodeCount`

- **Output**
  - smartart/@nodes.

- **OOXML**
  - Parsed nodes.

- **IR**
  - `int`

- **Parsing**
  - len(nodes).

### `links`

- **Output**
  - Resource graph connections.

- **OOXML**
  - cxn/@fromModelId and @toModelId.

- **IR**
  - `list[SmartArtLink]`

- **Parsing**
  - Resolve only nodes already seen in the same traversal. Current PPTX extractor does not read srcId/destId.

- **Diagnostics**
  - SMARTART_UNRESOLVED_LINK when either endpoint is unresolved; connection skipped.

### `linkCount`

- **Output**
  - smartart/@links.

- **OOXML**
  - Retained edges.

- **IR**
  - `int`

- **Parsing**
  - len(links).

### `truncated`

- **Output**
  - smartart/@truncated=true.

- **OOXML**
  - Serialization policy.

- **IR**
  - Derived.

- **Parsing**
  - Always true for inline summary.


## Source references

- [EmbeddedObjectExtractor._parse_diagram_data](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/resources/objects.py#L295)
- [SlideParser._smartart_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L640)
- [_append_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L54)
