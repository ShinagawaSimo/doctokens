# Connectors

[PPTX](../README.md) / Connectors

Connectors describe relationships between retained slide shapes.

`from-shape` and `to-shape` describe saved start/end attachments. They do not by
themselves assert a business-flow direction. Missing attachments are not guessed
from nearby shapes.

## Fields

### `fromShape`

- **Output**
  - `shape/@from-shape` in both XML densities.

- **OOXML**
  - First stCxn/@id.

- **IR**
  - `ShapeBlock.fromShape: str`

- **Parsing**
  - Resolve source drawing cNvPr ID to parsed shape ID; remove unresolved endpoint; update after final renumbering.
  - Match the target primary element's `shape-id` in the same slide. Do not
    resolve this field against an image/chart/media resource `id`.

### `toShape`

- **Output**
  - `shape/@to-shape` in both XML densities.

- **OOXML**
  - First endCxn/@id.

- **IR**
  - `ShapeBlock.toShape: str`

- **Parsing**
  - Same resolution as fromShape.

### `head-end` and `tail-end`

- **Output**
  - Connector attributes in structural and semantic output.
- **OOXML**
  - Non-`none` `a:headEnd/@type` and `a:tailEnd/@type` respectively.
- **IR**
  - `ShapeBlock.headEnd` and `ShapeBlock.tailEnd`.
- **Parsing**
  - Copy the source end-style declarations. Preserve arrow-bearing connectors
    even when an endpoint is unattached. Do not translate these fields into
    inferred relationships or apply a visual direction without its geometry.
