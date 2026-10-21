# SmartArt

[DOCX](../README.md) / SmartArt

SmartArt preserves nonempty labels and connections between those retained labels.

## Fields

### `id`

- **Output**
  - `smartart/@id`.

- **OOXML**
  - diagramData relationship traversal.

- **IR**
  - `SmartArt.id: str`

- **Parsing**
  - smartart1, smartart2, ...; missing targets can leave gaps.

- **Diagnostics**
  - `SMARTART_TARGET_MISSING`, `SMARTART_PARSE_FAILED`.

### `layoutType`

- **Output**
  - `smartart/@type`.

- **OOXML**
  - First dgm:cat/@type in related diagramLayout.

- **IR**
  - `SmartArt.layoutType: str`

- **Parsing**
  - Trim trailing slash; take final URI segment. Layout map is keyed by source part, so several diagrams in one source part can share/overwrite this category.

- **Absence and defaults**
  - Omitted.

- **Diagnostics**
  - `LAYOUT_PARSE_FAILED` on layout parsing failure.

### `part`

- **Output**
  - Resource locator.

- **OOXML**
  - Resolved diagramData target.

- **IR**
  - `SmartArt.part: str`

- **Parsing**
  - Require internal existing part.

### `sourcePart`

- **Output**
  - Internal relation owner.

- **OOXML**
  - Relationship source part.

- **IR**
  - `SmartArt.sourcePart: str`

- **Parsing**
  - Copy.

### `relationshipId`

- **Output**
  - Internal relation identity.

- **OOXML**
  - Relationship @Id.

- **IR**
  - `SmartArt.relationshipId: str`

- **Parsing**
  - Copy.

### `nodes`

- **Output**
  - Explicit body `node` elements and detailed resource nodes. Body and resource
    links reference one-based node ordinals.

- **OOXML**
  - `dgm:pt` descendants.

- **IR**
  - `list[SmartArtNode]`

- **Parsing**
  - Preserve every point, including empty/root/transition nodes, in source order.
    Empty labels do not remove connection endpoints. All reading plans retain the
    parsed edges; low-density summaries do not discard the graph.

### `nodeCount`

- **Output**
  - `smartart/@nodes`.

- **OOXML**
  - Retained nodes.

- **IR**
  - `SmartArt.nodeCount: int`

- **Parsing**
  - `len(nodes)`.

### `links`

- **Output**
  - Explicit body/resource edges referring to local node ordinals.

- **OOXML**
  - `dgm:cxn` descendants.

- **IR**
  - `list[SmartArtLink]`

- **Parsing**
  - Retain edges whose standard srcId/destId or supported producer aliases both
    resolve to retained nodes. All reading plans retain the graph. Duplicate
    source node ids bind references to their first occurrence.

### `linkCount`

- **Output**
  - `smartart/@links`.

- **OOXML**
  - Retained links.

- **IR**
  - `SmartArt.linkCount: int`

- **Parsing**
  - `len(links)`; reading summaries do not reduce the edge list.

### `rawLinkCount`

- **Output**
  - Internal/source-graph count.

- **OOXML**
  - All dgm:cxn descendants.

- **IR**
  - `SmartArt.rawLinkCount: int`

- **Parsing**
  - Count even connections with unresolved endpoints.

### `truncated`

- **Output**
  - `smartart/@truncated="true"`.

- **OOXML**
  - Serializer policy.

- **IR**
  - Derived.

- **Parsing**
  - Omitted for a retained graph; true for an unresolved object placeholder.
  - Body/resource `incomplete=true` indicates saved connections whose endpoints
    could not be resolved; this is distinct from output-budget truncation.
