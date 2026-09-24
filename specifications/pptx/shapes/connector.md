# Connectors

[PPTX](../README.md) / Connectors

Connectors describe relationships between retained slide shapes.

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

### `toShape`

- **Output**
  - `shape/@to-shape` in both XML densities.

- **OOXML**
  - First endCxn/@id.

- **IR**
  - `ShapeBlock.toShape: str`

- **Parsing**
  - Same resolution as fromShape.


## Source references

- [SlideParser._connector_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L323)
- [SlideParser._resolve_connector_endpoints](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L348)
- [_append_shape](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L54)
