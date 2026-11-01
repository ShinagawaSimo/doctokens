# SmartArt

[DOCX](../README.md) / SmartArt

SmartArt retains readable nodes and all resolved connection endpoints, including
empty root/transition endpoints. Reading bodies use a bounded preview; resources
return the complete retained reading graph without source GUIDs.

## Processing

Plain uses `[SmartArt: Start; Middle; End]`, omitting node numbers, edge listings
and layout/count bookkeeping. Both XML densities share the same preview limits:
12 source nodes, 24 connections and 1,200 label characters, including an ellipsis
when a label must be cut. Preserve source order and original node ordinals.
Keep only edges whose two endpoints are shown; never connect through a hidden
node or infer business order. Empty connected nodes consume slots and remain in
XML; isolated whitespace-only nodes are removed before applying the budget.
Plain uses the same node/label budget and omits empty labels.

A small graph is complete when all three limits fit. Otherwise body
`truncated=true` identifies a preview and @id resolves through
`session.render_resource("smartart", id)`. Plain uses
`[SmartArt id=smartart1 truncated: ...]`. Resource output has no body-preview
limit and remains unchanged after repeated body reads. IDs and endpoints agree
between the body and complete resource. A missing/unreadable graph retains an
unsupported child or `[Unparsed SmartArt]`, without a fabricated resource ID.

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
  - Assign source ordinals before filtering; keep every readable point and every
    endpoint of a resolved edge, including empty root/transition nodes. Remove
    only isolated whitespace-only points. Do not compact IDs or infer edges.
    The same reading graph feeds all densities and resources; preview selection
    occurs at rendering. Keep saved node/link kind as explicitly requested.

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
  - Retain edges whose standard srcId/destId both
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
  - `len(links)` in the complete parsed graph, even when the body previews fewer.

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
  - Omitted for a complete body graph; true when node, edge or label budgets
    omit content. A clipped node also has truncated=true. Resources have no
    body-budget truncation. Unreadable data uses unsupported, not truncated.
  - Body/resource `incomplete=true` indicates saved connections whose endpoints
    could not be resolved; this is distinct from output-budget truncation.
