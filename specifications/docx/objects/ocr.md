# Image OCR association

[DOCX](../README.md) / Image OCR association

OCR is performed only when an adapter is supplied and the parse plan includes OCR.

## Fields

### `id`

- **Output**
  - Sibling `<ocr-text id="img1">...</ocr-text>`.

- **Source**
  - Indexed image resource.

- **IR**
  - `ParsedDocument.ocr_results[asset_id]`

- **Parsing**
  - Associate by asset ID. Emit after each inline image and after each asset-list image; repeated references can repeat OCR text.

### `text`

- **Output**
  - ocr-text character data.

- **Source**
  - Adapter result.

- **IR**
  - `OcrStoredResult`

- **Parsing**
  - Use [common OCR](../../common/ocr.md); nonempty recognized text wins.

### `empty`

- **Output**
  - `ocr-text/@empty="true"`.

- **Source**
  - Empty adapter result.

- **IR**
  - `status == "empty"`

- **Parsing**
  - Emit only when recognized text is empty.

### `error`

- **Output**
  - `ocr-text/@error="true"`.

- **Source**
  - Stored error result.

- **IR**
  - Nonempty result entry without text or empty status.

- **Parsing**
  - Emit error marker. Current DOCX DTX OCR emission is not density-gated; a session retaining OCR can emit it at structural density.


## Source references

- [_append_ocr](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx_content.py#L49)
