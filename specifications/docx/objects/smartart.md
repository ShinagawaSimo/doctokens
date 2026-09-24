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
  - Space-joined inline labels; detailed resource nodes.

- **OOXML**
  - `dgm:pt` descendants.

- **IR**
  - `list[SmartArtNode]`

- **Parsing**
  - Keep only points with nonempty stripped concatenation of a:t; preserve point order.

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
  - Resource edges; no inline edge elements.

- **OOXML**
  - `dgm:cxn` descendants.

- **IR**
  - `list[SmartArtLink]`

- **Parsing**
  - Retain only edges whose srcId and destId both resolve to retained nodes. Summary plan discards the list.

### `linkCount`

- **Output**
  - `smartart/@links`.

- **OOXML**
  - Retained links.

- **IR**
  - `SmartArt.linkCount: int`

- **Parsing**
  - `len(links)` before summary reduction.

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
  - Always true on inline summary.


## Source references

- [parse_smartart_root](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/objects.py#L251)
- [EmbeddedObjectExtractor._build_layout_map](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/objects.py#L52)
- [_append_smartart](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L226)
