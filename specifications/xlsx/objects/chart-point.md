# Chart points

[XLSX](../README.md) / Chart points

Point records preserve saved string values.

Literal strLit/numLit points and strRef/numRef caches feed the same arrays. Match categories, values, scatter x/y, and bubble sizes by their saved point indices rather than XML child order. Missing intermediate positions remain empty records; a declared count alone does not invent values. Full chart resources retain all decoded positions, independently of the existing body-preview policy.

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
