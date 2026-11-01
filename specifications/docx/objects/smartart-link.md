# SmartArt links

[DOCX](../README.md) / SmartArt links

Connections address retained node ordinals.

## Fields

### `from`

- **Output**
  - Resource source ordinal.

- **OOXML**
  - `dgm:cxn/@srcId`

- **IR**
  - `SmartArtLink["from"]: int`

- **Parsing**
  - Resolve modelId to the original 1-based source-point ordinal; omit a
    connection if unresolved. Every resolved endpoint survives node filtering.

### `to`

- **Output**
  - Resource destination ordinal.

- **OOXML**
  - `dgm:cxn/@destId`

- **IR**
  - `SmartArtLink["to"]: int`

- **Parsing**
  - Resolve by the same map; omit connection if unresolved.

### `kind`

- **Output**
  - Resource relation type.

- **OOXML**
  - `dgm:cxn/@type`

- **IR**
  - `SmartArtLink.kind: str`

- **Parsing**
  - Copy nonempty value.
