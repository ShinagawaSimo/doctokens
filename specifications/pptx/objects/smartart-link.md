# SmartArt links

[PPTX](../README.md) / SmartArt links

Edges reference retained node ordinals.

## Fields

### `from`

- **Output**
  - Resource source.

- **OOXML**
  - dgm:cxn/@srcId.

- **IR**
  - `SmartArtLink["from"]: int`

- **Parsing**
  - Resolve prior modelId map; unresolved connection is omitted.

### `to`

- **Output**
  - Resource destination.

- **OOXML**
  - dgm:cxn/@destId.

- **IR**
  - `SmartArtLink["to"]: int`

- **Parsing**
  - Same prior-node resolution.

### `kind`

- **Output**
  - Saved nonempty link/@kind in body previews and resources.
- **OOXML**
  - dgm:cxn/@type.
- **IR**
  - SmartArtLink.kind: str.
- **Parsing**
  - Preserve the explicit relation clue. Standard parOf means parent-child;
    presOf/presParOf describe presentation relationships, not inferred business
    hierarchy; unknownRelationship declares an unknown relationship.
