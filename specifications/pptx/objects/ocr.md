# Image OCR association

[PPTX](../README.md) / Image OCR association

Semantic parsing/session can OCR referenced embedded image assets when an adapter is supplied.

## Fields

### `id`

- **Output**
  - Semantic sibling ocr-text/@id.

- **Source**
  - Picture assetId; background assetId only when background IR exists.

- **IR**
  - `ParsedPresentation.ocr_results` keys.

- **Parsing**
  - Deduplicate byte reads by zipPath, copy result to each asset ID; only referenced embedded image assets participate.

### `text`

- **Output**
  - ocr-text text.

- **Source**
  - Common OCR result.

- **IR**
  - `OcrStoredResult`

- **Parsing**
  - Emit recognized text after picture. No plain/structural OCR projection.

### `empty`

- **Output**
  - ocr-text/@empty=true.

- **Source**
  - status empty.

- **IR**
  - Result record.

- **Parsing**
  - Emit empty marker when no recognized text.

### `error`

- **Output**
  - ocr-text/@error=true.

- **Source**
  - Stored error result.

- **IR**
  - Result record.

- **Parsing**
  - Emit error marker; provider diagnostics remain in IR. See [OCR](../../common/ocr.md).


## Source references

- [PptxParser._run_ocr](../../../packages/pptx_llm_parser/src/pptx_llm_parser/parsing/runner.py#L431)
- [_append_ocr](../../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L225)
