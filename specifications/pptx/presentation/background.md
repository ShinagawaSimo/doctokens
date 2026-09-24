# Backgrounds

[PPTX](../README.md) / Backgrounds

Background extraction requires the internal GEOMETRY feature, absent from all public render and session plans.

## Fields

### `color`

- **Output**
  - Semantic slide/@background-color if populated.

- **OOXML**
  - Explicit p:cSld/p:bg descendant color.

- **IR**
  - `SlideBackground.color: str`

- **Parsing**
  - First resolved color. Does not inherit a missing slide background from layout/master.

### `assetId`

- **Output**
  - Semantic slide/@background-image if populated.

- **OOXML**
  - First background blip/@r:embed, fallback @r:link.

- **IR**
  - `SlideBackground.assetId: str`

- **Parsing**
  - Resolve asset index. Missing → BACKGROUND_ASSET_MISSING.


## Source references

- [SlideParser._background](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/modules/slides/scanner.py#L190)
- [PptxParsePlan.session](../../../packages/pptx_llm_parser/src/pptx_llm_parser/plan.py#L74)
