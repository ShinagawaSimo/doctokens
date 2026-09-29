# Style ranges

[XLSX](../README.md) / Style ranges

Repeated color/fill styles can be emitted once per rectangular region.

## Fields

### `ref`

- **Output**
  - `style-range/@ref`.

- **OOXML**
  - Visible emitted cells including merge spans.

- **IR**
  - Derived coordinates grouped by exact style string.

- **Parsing**
  - Group non-shadow cells only if style contains color= or fill=. Expand their colspan/rowspan into coordinate sets. If at least6 coordinates share the exact style, construct horizontal runs and merge identical spans over consecutive rows.

### `style attributes`

- **Output**
  - bold/italic/underline/color/fill on style-range.

- **OOXML**
  - FormatIndex.style_attrs.

- **IR**
  - Parsed attribute dictionary.

- **Parsing**
  - Sort styles lexically; sort rectangles by first row/column then end row/column. Suppress identical per-cell style attributes for the entire qualifying style group.


## Source references

- [_style_range_records](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/style_ranges.py#L12)
- [_rectangular_ranges](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/style_ranges.py#L38)
