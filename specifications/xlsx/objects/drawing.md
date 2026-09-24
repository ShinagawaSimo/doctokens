# Drawing anchors

[XLSX](../README.md) / Drawing anchors

Only the first worksheet drawing relationship is scanned.

## Processing

Missing drawing → DRAWING_PART_MISSING. Invalid relationship XML → DRAWING_RELS_XML_INVALID and continue with collected relationships. Invalid drawing XML → DRAWING_XML_INVALID, no objects.

## Fields

### `ref`

- **Output**
  - Image/chart @ref.

- **OOXML**
  - xdr:from/xdr:col and xdr:row.

- **IR**
  - `DrawingImage.ref`, `DrawingChart.ref: str`

- **Parsing**
  - Source coordinates are zero-based; convert to A1 with +1. Missing from (including absoluteAnchor) → empty string. Invalid integer coordinates propagate ValueError.

### `order`

- **Output**
  - Resource numbering order.

- **OOXML**
  - Drawing anchors.

- **IR**
  - images/charts list order.

- **Parsing**
  - Process all twoCellAnchor nodes, then oneCellAnchor, then absoluteAnchor; preserve order within each kind. This is grouped traversal rather than arbitrary document order.


## Source references

- [parse_drawings](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L420)
- [_parse_drawing_anchor](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L476)
