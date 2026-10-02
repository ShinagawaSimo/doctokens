# Results

[Agent tools](README.md) / Results

## Fields

### Envelope

- **Output**
  - `ok`, `data`, and optional `error`. Document results carry `document_id`, SHA-256 `revision`, original `path`, and `format`.
  - Text parts identify `density`, `selection`, `syntax_version`, `media_type`, warning count, length, and completeness/fragment status. Parser diagnostics remain available through document inspection.
- **Processing**
  - Large JSON metadata is itself stored as `application/json`; the response points to `read_result`.

### `text` and `result_id`

- **Default**
  - Body text budget: 12,000 characters, not a token estimate. Fixed identifiers/metadata and MCP compatibility projections add protocol overhead.
- **Processing**
  - Include complete selected text when the selection fits the budget; otherwise return stored result IDs and `next_action="read_result"`.
  - Each DOCX page remains an independent document. Do not concatenate XML roots and interpret the result as one XML document.
  - Stored IDs may expire or be evicted. Repeat the original read to regenerate a missing result.

### `offset`, `length`, and `next_offset`

- **Source**
  - Offset is zero-based and nonnegative; length is positive.
- **Default**
  - Requested chunk length: 8,000. Maximum requested length: 32,000, further bounded by reply budget.
- **Processing**
  - Text uses Python Unicode characters; binary uses bytes. Text chunks may split XML tags and always declare `fragment=true`, retaining the original syntax metadata.
  - `next_offset=null` marks the end. Joining text chunks in offset order reproduces the complete stored text without normalization.
  - Binary fragments declare `encoding="base64"`; decode each fragment then join bytes. Bounds beyond the result end are rejected; an offset exactly at end returns an empty final fragment.

### Binary attachments

- **Output**
  - Original embedded bytes and a MIME type. External resources are not fetched.
- **Default**
  - At most 256 KiB inline; larger values use `result_id`.
- **Processing**
  - Prefer descriptor content type, then the package-part extension, then `application/octet-stream`.
  - MCP emits supported PNG/JPEG/WebP/GIF as native image content and other small binary values as embedded blob resources. Direct callers receive `BinaryAttachment` objects.

### Errors

- **Output**
  - Stable `error.code` and explanatory `error.message`; MCP also sets `isError=true`.
- **Codes**
  - `INVALID_ARGUMENT`, `UNKNOWN_TOOL`, `PATH_NOT_ALLOWED`, `DOCUMENT_NOT_FOUND`, `UNSUPPORTED_FORMAT`, `FORMAT_MISMATCH`.
  - `SOURCE_CHANGED`, `DOCUMENT_EXPIRED`, `RESULT_EXPIRED`, `DOCUMENT_TOO_LARGE`, `RESULT_TOO_LARGE`, `CAPACITY_EXCEEDED`.
  - `RESOURCE_NOT_FOUND`, `EXTERNAL_RESOURCE`, `OCR_UNAVAILABLE`, `INVALID_DOCUMENT`, `IO_ERROR`, `RUNTIME_CLOSED`, `INTERNAL_ERROR`.
  - Unexpected failures log to stderr; the response does not include a traceback.
