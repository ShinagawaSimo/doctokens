# DrawingML colors

[PPTX](../README.md) / DrawingML colors

Resolved colors are normalized to #RRGGBB.

## Processing

Apply recognized child transforms in XML order. Invalid/non-finite numeric transforms: COLOR_VALUE_INVALID, preserve color through the failed operation. Text default-color filter suppresses black and RGB colors with max(channel)<=48 and max-min<=16.

## Fields

### `srgbClr`

- **Output**
  - Semantic color value.

- **OOXML**
  - a:srgbClr/@val.

- **IR**
  - Resolved str | None.

- **Parsing**
  - Require exactly six hex digits; uppercase with # prefix.

### `schemeClr`

- **Output**
  - Semantic color value.

- **OOXML**
  - a:schemeClr/@val.

- **IR**
  - LayoutContext.theme/color_map.

- **Parsing**
  - Map slot via color_map, then theme; reject missing or malformed hex.

### `sysClr`

- **Output**
  - Semantic color value.

- **OOXML**
  - a:sysClr/@lastClr.

- **IR**
  - Resolved str | None.

- **Parsing**
  - Use lastClr; no operating-system lookup.

### `prstClr`

- **Output**
  - Semantic color value.

- **OOXML**
  - a:prstClr/@val.

- **IR**
  - Resolved str | None.

- **Parsing**
  - Exact _PRESET_COLORS lookup; unknown → None.

### `hslClr`

- **Output**
  - Semantic color value.

- **OOXML**
  - @hue, @sat, @lum.

- **IR**
  - Resolved str | None.

- **Parsing**
  - Require finite numbers; hue/60000 modulo360, sat/100000, lum/100000; HSL conversion and channel clamp.

### `scrgbClr`

- **Output**
  - Semantic color value.

- **OOXML**
  - @r, @g, @b.

- **IR**
  - Resolved str | None.

- **Parsing**
  - Require finite values; round(value/100000*255), clamp each channel 0..255.

### `tint`

- **Output**
  - Transformed color.

- **OOXML**
  - Color child a:tint/@val.

- **IR**
  - RGB channels.

- **Parsing**
  - factor=val/100000; channel=round(c*(1-factor)+255*factor), clamped.

### `shade`

- **Output**
  - Transformed color.

- **OOXML**
  - a:shade/@val.

- **IR**
  - RGB channels.

- **Parsing**
  - factor=val/100000; channel=round(c*(1-factor)), clamped.

### `lumMod`

- **Output**
  - Transformed color.

- **OOXML**
  - a:lumMod/@val, first a:lumOff/@val.

- **IR**
  - HSL luminance.

- **Parsing**
  - L=clamp(L*lumMod/100000+lumOff/100000). lumOff alone does not alter color in this implementation.

### `alpha`

- **Output**
  - No color change.

- **OOXML**
  - a:alpha/@val.

- **IR**
  - Not retained.

- **Parsing**
  - Transparency is ignored.


## Source references

- [resolve_color_element](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/colors.py#L203)
- [_apply_transforms](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/colors.py#L236)
- [is_default_text_color](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/colors.py#L190)
