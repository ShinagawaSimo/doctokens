# SmartArt nodes

[PPTX](../README.md) / SmartArt nodes

Original source-point ordinals identify body/resource endpoints. Source modelId
is used only during edge resolution and is absent from the reading model/output.

## Fields

### `id`

- **Output**
  - Resource node ordinal.

- **OOXML**
  - pt encounter order.

- **IR**
  - `SmartArtNode.id: int`

- **Parsing**
  - Assign before filtering and map a nonempty source modelId to its first
    occurrence. Remove only isolated whitespace-only nodes. Body previews and
    resources keep original ordinals, including gaps, rather than renumbering.

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

### `kind`

- **Output**
  - Saved nonempty node/@kind in both XML densities and resources.
- **OOXML**
  - dgm:pt/@type.
- **IR**
  - SmartArtNode.kind: str.
- **Parsing**
  - Preserve the explicit type. Standard types include node, asst (assistant),
    doc (root), pres, parTrans and sibTrans. This is a diagram-model clue, not
    an inferred business role. Connected empty nodes retain their kind.
