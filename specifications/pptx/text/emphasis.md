# Text emphasis

[PPTX](../README.md) / Text emphasis

Semantic DTX nests wrappers in the order color, highlight, strike, baseline,
underline, italic, bold, hyperlink. Adjacent runs merge only when all effective
public formats and the hyperlink agree.

## Processing

Semantic/session inheritance: master and layout style → shape role/type/idx → txBody lstStyle → paragraph defRPr → run rPr. Merge direct dictionaries in that order. Plain/structural one-shot parsing omits formatting/theme resolution.

## Fields

### `bold`

- **Output**
  - `<b>...</b>`.

- **OOXML**
  - a:rPr/@b; inherited a:defRPr/@b.

- **IR**
  - `Run.format.bold: bool`

- **Parsing**
  - Present attribute → lower-case value outside 0/false/off/no is true.
    False overrides inherited true. DrawingML stores this as an attribute.

### `italic`

- **Output**
  - `<i>...</i>`.

- **OOXML**
  - a:rPr/@i; inherited a:defRPr/@i.

- **IR**
  - `Run.format.italic: bool`

- **Parsing**
  - Same boolean rule as bold.

### `underline`

- **Output**
  - `<u>...</u>`.

- **OOXML**
  - a:rPr/@u; inherited a:defRPr/@u.

- **IR**
  - `Run.format.underline: bool`

- **Parsing**
  - The DrawingML value none clears inherited underline; other saved line
    styles retain underline semantics without reproducing their geometry.

### `strike`

- **Output**
  - `<s>...</s>` in semantic output.
- **OOXML**
  - a:rPr/@strike; inherited a:defRPr/@strike.
- **IR**
  - `Run.format.strike: bool`.
- **Parsing**
  - sngStrike and dblStrike enable the reading property; noStrike clears it.
    The number of strokes is not an editable-layout projection.

### `superscript`

- **Output**
  - `<sup>...</sup>` in semantic output.
- **OOXML**
  - a:rPr/@baseline; inherited a:defRPr/@baseline.
- **IR**
  - `Run.format.superscript: bool`.
- **Parsing**
  - A positive saved integer enables superscript and clears subscript.
    Zero clears both. A non-integer emits TEXT_BASELINE_INVALID and leaves
    readable text and inherited formatting available; no element placeholder
    is added for a failed format value. The offset magnitude is not emitted.

### `subscript`

- **Output**
  - `<sub>...</sub>` in semantic output.
- **OOXML**
  - The same baseline attribute.
- **IR**
  - `Run.format.subscript: bool`.
- **Parsing**
  - A negative integer enables subscript and clears superscript.
    Example: x followed by a run containing 2 with baseline=30000 becomes
    `x<sup>2</sup>`; baseline=-25000 becomes `x<sub>2</sub>`.

### `highlight`

- **Output**
  - `<mark value="#RRGGBB">...</mark>` in semantic output.
- **OOXML**
  - a:rPr/a:highlight or inherited a:defRPr/a:highlight, with a color child.
- **IR**
  - `Run.format.highlight: str`.
- **Parsing**
  - Resolve the first readable color with the existing DrawingML color
    resolver. Black is a meaningful highlight and is retained. Missing
    highlight inherits; unsupported color encodings do not create a guessed
    highlight. Transparency follows the existing [color policy](color.md).

### `color`

- **Output**
  - `<color value="#RRGGBB">...</color>`.

- **OOXML**
  - a:rPr/a:solidFill color child.

- **IR**
  - `Run.format.color: str`

- **Parsing**
  - First resolved color; see [colors](color.md). A resolved default/near-black
    color clears inherited non-default color and emits no color wrapper.
    This same reader handles direct and inherited character properties.
