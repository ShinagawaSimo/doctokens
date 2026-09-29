# Geometry

[PPTX](../README.md) / Geometry

Geometry describes an internal parsing path, not a public density.

## Processing

Group scales are ext/chExt; offsets are off - chOff*scale. Compose nested transforms and round output. Rotation/flip are not applied. Invalid transforms produce GROUP_GEOMETRY_INVALID and use parent transform; malformed shape dimensions produce GEOMETRY_INVALID. Geometry-enabled shape sorting is stable by (y,x), unpositioned shapes last. Slide size is p:sldSz/@cx,@cy as integers; missing/invalid gives PRESENTATION_MISSING_SLDSZ/SLDSZ_INVALID.

## Fields

### `x`

- **Output**
  - Internal geometry; no public DTX attribute.

- **OOXML**
  - First xfrm/a:off/@x, fallback layout/master.

- **IR**
  - `ShapeBlock.x: int`

- **Parsing**
  - Apply group affine transform in EMU; `round(value / slide_width * 1000)`. Public plans do not request geometry.

### `y`

- **Output**
  - Internal geometry; no public DTX attribute.

- **OOXML**
  - First xfrm/a:off/@y, fallback layout/master.

- **IR**
  - `ShapeBlock.y: int`

- **Parsing**
  - Apply group affine transform in EMU; `round(value / slide_height * 1000)`. Public plans do not request geometry.

### `w`

- **Output**
  - Internal geometry; no public DTX attribute.

- **OOXML**
  - First xfrm/a:ext/@cx, fallback layout/master.

- **IR**
  - `ShapeBlock.w: int`

- **Parsing**
  - Apply group affine transform in EMU; `round(value / slide_width * 1000)`. Public plans do not request geometry.

### `h`

- **Output**
  - Internal geometry; no public DTX attribute.

- **OOXML**
  - First xfrm/a:ext/@cy, fallback layout/master.

- **IR**
  - `ShapeBlock.h: int`

- **Parsing**
  - Apply group affine transform in EMU; `round(value / slide_height * 1000)`. Public plans do not request geometry.


## Source references

- [_GroupTransform](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/geometry.py#L23)
- [SlideGeometry._group_transform](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/geometry.py#L143)
- [SlideGeometry._attach_inheritance](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/geometry.py#L109)
- [shape_geometry](../../../packages/pptx_llm_parser/src/pptx_llm_parser/ooxml/inheritance.py#L51)
