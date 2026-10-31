# SmartArt nodes

[PPTX](../README.md) / SmartArt nodes

Local node ordinals identify body/resource endpoints. The resource also retains
the source modelId under its existing source-id field.

## Fields

### `id`

- **Output**
  - Resource node ordinal.

- **OOXML**
  - pt encounter order.

- **IR**
  - `SmartArtNode.id: int`

- **Parsing**
  - len(nodes)+1; map a nonempty source modelId to its first occurrence.
    Body previews keep original ordinals rather than renumbering selected nodes.

### `text`

- **Output**
  - DTX inline label / resource node text.

- **OOXML**
  - Descendant local-name t.

- **IR**
  - `SmartArtNode.text: str`

- **Parsing**
  - Concatenate text including empty/whitespace results.
    Empty nodes remain graph endpoints. Only body previews can clip a label;
    the complete resource retains its saved text.
