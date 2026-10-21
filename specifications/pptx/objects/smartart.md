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
  - Explicit `node` elements in the body and resource data. Plain includes indexed labels.

- **OOXML**
  - DrawingML diagram `dgm:pt` descendants.

- **IR**
  - `list[SmartArtNode]`

- **Parsing**
  - Keep every pt, including empty/root/transition labels, in source order. Node
    ids are one-based positions; preserve source model ids in resource `source-id`
    and explicit node types in `kind`. Do not guess business-node roles.

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
  - Explicit body/resource `link` elements; plain lists saved endpoint pairs.

- **OOXML**
  - Standard `dgm:cxn/@srcId` and `@destId`; retain the previously supported
    producer aliases `fromModelId`/`toModelId` when standard fields are absent.

- **IR**
  - `list[SmartArtLink]`

- **Parsing**
  - Build the complete node index before resolving edges. Empty node ids do not
    bind a missing endpoint. On duplicate source ids, retain nodes but bind
    references to the first indexed occurrence.

- **Diagnostics**
  - SMARTART_UNRESOLVED_LINK when either endpoint is unresolved; connection skipped.
  - SMARTART_DUPLICATE_MODEL_ID for repeated source ids. Body/resource output
    declares `incomplete=true` when a saved connection cannot be retained.

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
  - Omitted when the complete parsed graph is present; true for an unresolved
    inline placeholder. Parsing failure is distinguished from budget truncation.
