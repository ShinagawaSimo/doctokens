# OCR

[COMMON](README.md) / OCR

DOCX and PPTX accept an explicitly supplied OCR provider. XLSX exposes no OCR option.

## Processing

OCR executes at body-read time after the requested page/slide and current
density's retained image scope are selected. Opening a session, directories,
search and binary image reads do not initiate recognition. Each explicit session
owns a source-part result cache; closing it releases that cache. One-shot reads
have their own short-lived owner. There is no process-global OCR cache.

All three densities keep complete recognized text after every retained image
occurrence. Repeated appearances reuse recognition work but repeat the text.
Asset-directory declarations do not repeat it. There is no separate OCR excerpt
limit, deduplication reference or expansion into content intentionally omitted
by the current density. Existing result-transport limits remain independent.

## Fields

### `ocr`

- **Output**
  - Optional derived text.

- **Source**
  - Caller-provided object, not OOXML.

- **IR**
  - `ParseOptions.ocr: object | None = None`

- **Parsing**
  - Requires callable `extract_result(image_bytes, *, timeout=...)` returning
    `ocr_llm_core.OcrResult`. No recognition occurs without a configured adapter.
    The batcher passes the timeout keyword directly.
  - String/mapping return values produce an `invalid_result` error. Parser IR stores `OcrResultRecord` dictionaries generated from the result; it does not accept a second string-result schema.

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
  - Successful text, or `ocr-text/@error="true"` / plain `[OCR failed]`.
    Successful empty results add no OCR node or plain marker.

- **Source**
  - Provider result.

- **IR**
  - `OcrResultRecord.status: Literal["success", "empty", "error"]`

- **Parsing**
  - Keep result separate from native text.

### `text`

- **Output**
  - Both XML densities: `<ocr-text id="img1">recognized text</ocr-text>`.
    Plain: a `[OCR]` line, complete recognized text and a `[/OCR]` closing marker
    following the image. The closing marker keeps subsequent native inline
    text outside the OCR block.

- **Source**
  - Provider text.

- **IR**
  - `OcrResultRecord.text: str`

- **Parsing**
  - Attach using the originating asset ID; not inserted into native run text.
    Preserve complete text, including internal line breaks. Independent reads
    remain self-contained even when a prior read populated the session cache.

### `low_confidence`

- **Output**
  - `<ocr-text low-confidence="true">...</ocr-text>` or plain
    `[OCR low-confidence]` opening marker. Scores are absent from document text, OCR
    records and reading result metadata.
- **Source**
  - Available engine recognition scores; do not substitute layout/detection
    scores or infer confidence from recognized words.
- **Normalization**
  - Normalize valid recognition scores to 0..1. For word/block scores use
    non-whitespace character counts as weights. Exclude missing, non-finite,
    out-of-range and sentinel scores; exclude zero-character records. Only
    available scored text participates in the average.
  - Strictly less than 0.8 adds the hint; equality does not. This is a reading
    warning threshold, not an accuracy estimate. Absence of a hint does not
    imply high confidence when no usable score exists.
- **Adapters**
  - EasyOCR reads detailed text/recognition-score records. Tesseract preserves
    complete TXT and reads word confidences from TSV, dividing 0..100 by 100.
    Prefer a combined TXT/TSV invocation; older clients can use an optional
    score pass within the remaining timeout. A score-pass failure preserves
    available text without guessing a score.
  - PaddleOCR-VL's current Markdown path supplies no reliable recognition score;
    its text remains readable without a confidence hint. Custom adapters can
    supply normalized image confidence using the same weighted rule.
- **IR**
  - `OcrResult.confidence` is optional adapter-internal data. `to_record()`
    projects only a low_confidence boolean; raw values are not retained in
    document/session result records.

### `error_code`

- **Output**
  - Provider diagnostic; not native document text.

- **IR**
  - `OcrResultRecord.error_code: str`

- **Parsing**
  - Retain if supplied; main DTX emits only the error state. A fresh failed
    source-part attempt adds OCR_FAILED to diagnostics, once per session cache
    entry rather than once per repeated picture occurrence.

### `error_message`

- **Output**
  - Provider diagnostic; not native document text.

- **IR**
  - `OcrResultRecord.error_message: str`

- **Parsing**
  - Retain if supplied; main DTX does not expose this message.
