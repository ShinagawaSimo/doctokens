# OCR

[COMMON](README.md) / OCR

DOCX and PPTX accept an explicitly supplied OCR provider. XLSX exposes no OCR option.

## Fields

### `ocr`

- **Output**
  - Optional derived text.

- **Source**
  - Caller-provided object, not OOXML.

- **IR**
  - `ParseOptions.ocr: object | None = None`

- **Parsing**
  - Requires callable `extract(image_bytes)` or `extract_result(image_bytes)`; invoked only when the plan enables OCR.

- **Diagnostics**
  - Invalid provider: `TypeError`.

### `ocr_workers`

- **Output**
  - Concurrency limit.

- **IR**
  - `int = 4`

- **Parsing**
  - Positive integer excluding bool.

- **Diagnostics**
  - Invalid: `ValueError`.

### `ocr_timeout`

- **Output**
  - Timeout in seconds.

- **IR**
  - `float = 120.0`

- **Parsing**
  - Positive finite int/float excluding bool.

- **Diagnostics**
  - Invalid: `ValueError`.

### `status`

- **Output**
  - `ocr-text/@empty="true"` or `@error="true"`, or successful text.

- **Source**
  - Provider result.

- **IR**
  - `OcrResultRecord.status: Literal["success", "empty", "error"]`

- **Parsing**
  - Keep result separate from native text.

### `text`

- **Output**
  - `<ocr-text id="img1">recognized text</ocr-text>`.

- **Source**
  - Provider text.

- **IR**
  - `OcrResultRecord.text: str`

- **Parsing**
  - Attach using the originating asset ID; not inserted into native run text.

### `error_code`

- **Output**
  - Provider diagnostic; not native document text.

- **IR**
  - `OcrResultRecord.error_code: str`

- **Parsing**
  - Retain if supplied; main DTX emits the error state rather than this code.

### `error_message`

- **Output**
  - Provider diagnostic; not native document text.

- **IR**
  - `OcrResultRecord.error_message: str`

- **Parsing**
  - Retain if supplied; main DTX does not expose this message.


## Source references

- [PackageOptions.validate_ocr_options](../../packages/ooxml_llm_core/src/ooxml_llm_core/options.py#L32)
- [_append_ocr](../../packages/docx_llm_parser/src/docx_llm_parser/rendering/dtx.py#L306)
- [_append_ocr](../../packages/pptx_llm_parser/src/pptx_llm_parser/rendering/dtx.py#L225)
