# Parse manifest

[PPTX](README.md) / Parse manifest

`ParseResult.report.manifest` describes parsed content before rendering. Page/slide selection does not recalculate these counts.

## Fields

### `slideCount`

- **Output**
  - `report.manifest["slideCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_presentation`

- **Parsing**
  - `len(parsed_presentation.slides)`

- **Notes**
  - Accepted slides, including hidden slides.

### `shapeCount`

- **Output**
  - `report.manifest["shapeCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_presentation`

- **Parsing**
  - `sum(len(slide["shapes"]) for slide in parsed_presentation.slides)`

- **Notes**
  - Shapes retained after source traversal and filtering.

### `imageCount`

- **Output**
  - `report.manifest["imageCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_presentation`

- **Parsing**
  - `sum(1 for asset in parsed_presentation.assets if asset.get("type") == "image")`

- **Notes**
  - Image assets.

### `mediaCount`

- **Output**
  - `report.manifest["mediaCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_presentation`

- **Parsing**
  - `sum(1 for asset in parsed_presentation.assets if asset.get("type") == "media")`

- **Notes**
  - Media assets.

### `chartCount`

- **Output**
  - `report.manifest["chartCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_presentation`

- **Parsing**
  - `len(parsed_presentation.charts)`

- **Notes**
  - Parsed charts.

### `smartartCount`

- **Output**
  - `report.manifest["smartartCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_presentation`

- **Parsing**
  - `len(parsed_presentation.smartarts)`

- **Notes**
  - Parsed SmartArt records.

### `commentCount`

- **Output**
  - `report.manifest["commentCount"]: int`

- **Source**
  - Parsed package content.

- **IR**
  - `parsed_presentation`

- **Parsing**
  - `len(parsed_presentation.comments)`

- **Notes**
  - Parsed comments.


## Source references

- [PptxParser.parse](../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/runner.py#L276)
