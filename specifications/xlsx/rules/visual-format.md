# Conditional visual formats

[XLSX](../README.md) / Conditional visual formats

Visual-format dictionaries retain source strings.

## Fields

### `stops`

- **Output**
  - Semantic details string.

- **OOXML**
  - colorScale/cfvo and color children.

- **IR**
  - `formatDetails["stops"]: list[dict[str,str]]`

- **Parsing**
  - Pair by position. Each cfvo retains type/val/gte; paired color chooses rgb then theme then indexed. Missing color leaves threshold only.

### `thresholds`

- **Output**
  - Semantic details string.

- **OOXML**
  - dataBar/cfvo or iconSet/cfvo.

- **IR**
  - `list[dict[str,str]]`

- **Parsing**
  - Keep direct cfvo children, preserving type/val/gte if present.

### `type`

- **Output**
  - Stop/threshold field.

- **OOXML**
  - cfvo/@type.

- **IR**
  - `str`

- **Parsing**
  - Copy source discriminator without evaluating it.

### `val`

- **Output**
  - Stop/threshold field.

- **OOXML**
  - cfvo/@val.

- **IR**
  - `str`

- **Parsing**
  - Core cfvo/@val supplies a literal/formula string. x14:cfvo uses direct
    xm:f text instead; map it to the same value field, including zero.

### `gte`

- **Output**
  - Stop/threshold field.

- **OOXML**
  - cfvo/@gte.

- **IR**
  - `str`

- **Parsing**
  - Copy present source string; no synthesized default.

### `color`

- **Output**
  - Stop/bar field.

- **OOXML**
  - color/@rgb, @theme, @indexed; x14 data bars also use fillColor.

- **IR**
  - `str`

- **Parsing**
  - First truthy in that order; color references are not resolved here.

### `minLength`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@minLength.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `maxLength`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@maxLength.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `showValue`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@showValue.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `gradient`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@gradient.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `border`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@border.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `direction`

- **Output**
  - Semantic details field.

- **OOXML**
  - dataBar/@direction.

- **IR**
  - `str`

- **Parsing**
  - Retain present attribute verbatim.

### `iconSet attributes`

- **Output**
  - Semantic details fields.

- **OOXML**
  - All iconSet attributes.

- **IR**
  - `dict[str,object]`

- **Parsing**
  - Copy complete attribute dictionary; add thresholds. Attribute vocabulary is open and source-defined.

### `negativeBarColorSameAsPositive`

- **Output**
  - Semantic data-bar details field.
- **OOXML**
  - x14:dataBar/@negativeBarColorSameAsPositive.
- **Parsing**
  - Retain a saved source boolean string; do not synthesize a color.

### `negativeBarBorderColorSameAsPositive`

- **Output**
  - Semantic data-bar details field.
- **OOXML**
  - x14:dataBar/@negativeBarBorderColorSameAsPositive.
- **Parsing**
  - Retain the saved flag independently of negative fill behavior.

### `axisPosition`

- **Output**
  - Semantic data-bar details field.
- **OOXML**
  - x14:dataBar/@axisPosition.
- **Parsing**
  - Retain the source value; do not derive a pixel coordinate.

### `borderColor`

- **Output**
  - Semantic data-bar details field.
- **OOXML**
  - x14:dataBar/x14:borderColor.
- **Parsing**
  - Retain the saved RGB/theme/indexed source color using the existing color
    reference policy. This reader does not evaluate the conditional style.

### `negativeFillColor`

- **Output**
  - Semantic data-bar details field.
- **OOXML**
  - x14:dataBar/x14:negativeFillColor.
- **Parsing**
  - Retain the saved source color.

### `negativeBorderColor`

- **Output**
  - Semantic data-bar details field.
- **OOXML**
  - x14:dataBar/x14:negativeBorderColor.
- **Parsing**
  - Retain the saved source color.

### `axisColor`

- **Output**
  - Semantic data-bar details field.
- **OOXML**
  - x14:dataBar/x14:axisColor.
- **Parsing**
  - Retain the saved source color.

### `icons`

- **Output**
  - Semantic icon-set details records.
- **OOXML**
  - x14:iconSet/x14:cfIcon attributes, including iconSet and iconId.
- **Parsing**
  - Preserve saved custom-icon order and attribute values alongside thresholds.
    Do not substitute a different built-in icon set. Serialize record lists
    with the existing colon-separated field and semicolon-separated record
    notation used for stops/thresholds.
