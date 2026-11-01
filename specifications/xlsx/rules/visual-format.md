# Conditional visual formats

[XLSX](../README.md) / Conditional visual formats

Semantic retains the meaning of saved visual emphasis without executing rules.
Structural retains rule types and conditions but omits visual details. Drawing
sizes, gradients, borders, axes and arbitrary source attributes are not extracted.

Formula text and format literals never use a delimiter subprotocol. No new truncation is imposed by this structural representation; existing range and density permissions remain.

## Fields

### `stops`

- **Output**
  - Semantic rule/color-scale/stop elements, in saved order.
- **OOXML**
  - Core/x14 colorScale/cfvo and color children, paired in source order.
- **IR**
  - `VisualDetails.stops: list[FormatThreshold]`.
- **Parsing**
  - Retain each threshold and its resolved color where available.

### `thresholds`

- **Output**
  - Semantic rule/data-bar/threshold or rule/icon-set/threshold elements.
- **OOXML**
  - Core/x14 dataBar/cfvo or iconSet/cfvo.
- **Parsing**
  - Preserve source order; do not calculate effective threshold values.

### `type`

- **Output**
  - Stop/threshold type.
- **OOXML**
  - cfvo/@type.
- **Parsing**
  - Preserve the saved discriminator: num/percent/percentile/formula,
    min/max/autoMin/autoMax, or an unknown source value.

### `val`

- **Output**
  - Stop/threshold @value, retaining the full literal or formula.
- **OOXML**
  - Core cfvo/@val; direct x14 cfvo/xm:f text takes precedence.
- **Parsing**
  - Keep values/formulas, including zero. Omit irrelevant saved values on
    min/max/autoMin/autoMax thresholds.

### `gte`

- **Output**
  - gte=false for an exclusive boundary; omit default true.
- **OOXML**
  - cfvo/@gte.
- **Parsing**
  - Normalize 0/false to false; omit 1/true. Retain unknown spellings.

### `color`

- **Output**
  - Semantic stop/bar color as #RRGGBB.
- **OOXML**
  - color or x14 fillColor nodes.
- **Parsing**
  - Resolve RGB/theme/indexed/tint with the workbook palette. Omit unresolved
    colors instead of emitting ambiguous palette indices. Invalid tint does
    not fall back to the unadjusted base. Emit XLSX_COLOR_UNRESOLVED at the rule's
    worksheet part, while retaining readable thresholds and other properties.
    This is a diagnostic, not an extra body attribute or an unreadable rule.

### `negativeFillColor`

- **Output**
  - Semantic data-bar/@negative-fill-color.
- **OOXML**
  - x14:dataBar/x14:negativeFillColor and @negativeBarColorSameAsPositive.
- **Parsing**
  - Retain a resolved saved negative color unless the source explicitly uses
    the positive color for negative values. Never synthesize a negative color.

### `showValue`

- **Output**
  - Semantic data-bar|icon-set/@show-value=false; omit default true.
- **OOXML**
  - dataBar/@showValue or iconSet/@showValue.
- **Parsing**
  - Preserve saved value hiding; the reading grid still retains cell content.

### `iconSet`

- **Output**
  - Semantic icon-set/@name alongside ordered threshold elements.
- **OOXML**
  - iconSet/@iconSet, default 3TrafficLights1.
- **Parsing**
  - The name identifies the visual vocabulary even at its default. No open
    attribute dictionary is retained.

### `reverse`

- **Output**
  - Semantic icon-set/@reverse=true; omit default false.
- **OOXML**
  - iconSet/@reverse.
- **Parsing**
  - Preserve reversal of the icon interpretation.

### `icons`

- **Output**
  - Semantic ordered icon-set/icon elements with @set and @id.
- **OOXML**
  - x14:iconSet/x14:cfIcon/@iconSet and @iconId.
- **Parsing**
  - Keep only set and ordinal, including NoIcons. Do not substitute a built-in
    icon set or copy unrelated source attributes.
