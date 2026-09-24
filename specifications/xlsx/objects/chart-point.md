# Chart points

[XLSX](../README.md) / Chart points

Point records preserve saved string values.

## Fields

### `category`

- **Output**
  - Resource point attribute; omit empty strings in resource output.

- **OOXML**
  - Shared series categories[index].

- **IR**
  - `ChartPoint.category: str`

- **Parsing**
  - Copy only when index is within the source list.

### `value`

- **Output**
  - Resource point attribute; omit empty strings in resource output.

- **OOXML**
  - Shared series values[index].

- **IR**
  - `ChartPoint.value: str`

- **Parsing**
  - Copy only when index is within the source list.

### `x`

- **Output**
  - Resource point attribute; omit empty strings in resource output.

- **OOXML**
  - Shared series x_values[index].

- **IR**
  - `ChartPoint.x: str`

- **Parsing**
  - Copy only when index is within the source list.

### `y`

- **Output**
  - Resource point attribute; omit empty strings in resource output.

- **OOXML**
  - Shared series y_values[index].

- **IR**
  - `ChartPoint.y: str`

- **Parsing**
  - Copy only when index is within the source list.

### `bubbleSize`

- **Output**
  - Resource point attribute; omit empty strings in resource output.

- **OOXML**
  - Shared series bubble_sizes[index].

- **IR**
  - `ChartPoint.bubbleSize: str`

- **Parsing**
  - Copy only when index is within the source list.


## Source references

- [_parse_chart_part](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L527)
