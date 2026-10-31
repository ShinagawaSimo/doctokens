# SmartArt

[PPTX](../README.md) / SmartArt

The diagram extractor uses its own node and connection conventions.

## Processing

Plain displays `[SmartArt: Start; Middle; End]`, omitting numbered labels, edge
listings and layout/count bookkeeping. Both XML densities use the same body
preview limits: 12 source nodes, 24 connections and 1,200 label characters,
including a trailing ellipsis when a label must be cut. Preserve source order,
original node IDs and empty/root/transition nodes. Empty nodes consume slots;
plain omits their empty labels. Only show edges with two retained endpoints;
do not fabricate a connection through a hidden node.

When the entire graph fits all limits, show it completely. Otherwise body
truncated=true identifies the preview and @id resolves with
`session.render_resource("smartart", id)`. Plain includes
`[SmartArt id=smartart1 truncated: ...]`. A clipped node has truncated=true.
Resource output remains complete, keeps its original node IDs and existing
source-id fields, and does not inherit body limits or mutate after body reads.
Missing/unreadable data retains an unsupported child or `[Unparsed SmartArt]`,
without inventing a readable resource key or budget-truncation flag.

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
  - Previewed body nodes and complete resource nodes. Plain includes readable labels.

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
  - Bounded body and complete resource `link` elements. Plain omits endpoint lists.

- **OOXML**
  - Standard `dgm:cxn/@srcId` and `@destId`.

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
  - True when body node, connection or label budgets omit content; otherwise
    omitted. Parsing failure retains unsupported rather than a truncation flag.
