# SmartArt links

[PPTX](../README.md) / SmartArt links

Edges reference retained node ordinals.

## Fields

### `from`

- **Output**
  - Resource source.

- **OOXML**
  - cxn/@fromModelId.

- **IR**
  - `SmartArtLink["from"]: int`

- **Parsing**
  - Resolve prior modelId map; unresolved connection is omitted.

### `to`

- **Output**
  - Resource destination.

- **OOXML**
  - cxn/@toModelId.

- **IR**
  - `SmartArtLink["to"]: int`

- **Parsing**
  - Same prior-node resolution.
