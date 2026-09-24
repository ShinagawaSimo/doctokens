# Hyperlinks and actions

[PPTX](../README.md) / Hyperlinks and actions

Targets are preserved as strings; no navigation action is executed.

## Fields

### `link`

- **Output**
  - Shape @link; run `<a href="...">`.

- **OOXML**
  - Shape cNvPr/a:hlinkClick, fallback hlinkHover; run a:rPr/a:hlinkClick.

- **IR**
  - `ShapeBlock.link`, `Run.link: str`

- **Parsing**
  - Shape: relationship target, then action. Run: if r:id exists, relationship lookup only; otherwise action. Missing run relation does not fall back to action.

### `slide anchor`

- **Output**
  - `#slideN` target.

- **OOXML**
  - Internal slide relationship or ppaction://hlinkshowjump?jump=.

- **IR**
  - Normalized link string.

- **Parsing**
  - Resolve part through validated presentation references. nextslide/previousslide clamp at ends; firstslide/lastslide resolve similarly. Invalid slide XML can leave reference-based target numbering different from accepted-slide numbering.


## Source references

- [_run_link](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L1088)
- [SlideParser._attach_shape_navigation](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L265)
- [_normalize_slide_navigation](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/runner.py#L77)
