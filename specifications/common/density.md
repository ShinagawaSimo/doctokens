# Density

[COMMON](README.md) / Density

Density selects a format-specific extraction plan and output projection.

## Processing

| Feature | DOCX plain / structural | DOCX semantic / session |
| --- | --- | --- |
| Body, image index, notes, comments, object summaries | Yes | Yes |
| Run formatting, headers/footers, comment threading, object details, optional OCR | No | Yes |
| Raw hints | No | Session only, subject to options |

| Feature | PPTX plain / structural | PPTX semantic / session |
| --- | --- | --- |
| Slide index, text, images, notes, comments, navigation, objects | Yes | Yes |
| Text formatting, theme/layout, optional OCR | No | Yes |
| Geometry sorting and background extraction | No | No |

| Feature | XLSX plain | XLSX structural | XLSX semantic / session |
| --- | --- | --- | --- |
| Values, comments, rules, tables, drawings, pivots, rich values, controls | Yes | Yes | Yes |
| Formula text, hyperlinks, names, external links, style indices | No | Yes | Yes |
| Rich text and semantic styles | No | No | Yes |

XLSX number-format display processing is available in every density. Resource identifiers and diagnostics are plan-dependent; comparisons across plans must use the source owner and reference, not assume identical resource numbering.

## Fields

### `density`

- **Output**
  - `plain`: `doctokens-plain/1.0`, `text/plain`.
  - `structural`, `semantic`: `doctokens-xml/1.0`, `application/xml`.

- **Source**
  - Call argument; no OOXML attribute.

- **IR**
  - `Literal["plain", "structural", "semantic"]`

- **Parsing**
  - DOCX/PPTX default: `semantic`. XLSX default: `structural`.
  - One-shot plans omit unused work; sessions retain semantic-level data for subsequent projections.

- **Diagnostics**
  - Other values: `ValueError`.


## Source references

- [plan.py](../../packages/docx_llm_parser/src/docx_llm_parser/plan.py)
- [plan.py](../../packages/pptx_llm_parser/src/pptx_llm_parser/plan.py)
- [plan.py](../../packages/xlsx_llm_parser/src/xlsx_llm_parser/plan.py)
