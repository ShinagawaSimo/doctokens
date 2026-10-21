# Results

[Agent tools](README.md) / Results

## Fields

### Envelope

- **Output**
  - `ok`, `data`, and optional `error`. Reading results carry `document_id` for
    the pinned snapshot, selected intervals and text parts. Do not repeat input
    paths, hashes, density/version declarations, cache-hit flags or default/null
    state. Explicit full inspection supplies source revision/path and diagnostics.
  - A text part identifies `selection` and `media_type`. The envelope includes
    unique warning codes only when present; full diagnostics are opt-in.
- **Processing**
  - Large JSON metadata is stored as `application/json`; its first fragment is
    returned immediately with an actionable result id and next offset.

### `text` and `result_id`

- **Default**
  - Body text budget: 12,000 Unicode characters, not a token estimate. Bounded
    selection metadata and native MCP framing add protocol overhead.
- **Processing**
  - Return complete selected text when it fits; otherwise return a first prefix
    and `result_id`/`next_offset` for each incomplete part. Distribute one body
    budget across parts in order; a later unstarted part has next_offset=0 and
    no text. A complete part omits continuation fields and does not advertise an
    unused result id. The first-content budget is bounded by reply_chars and
    max_chunk_size.
  - Direct `ToolRuntime` calls put text in `parts[].text` (or root `text` for a
    continuation/JSON fragment). MCP puts it only in native `TextContent`; the
    structured counterpart supplies `content_index`. Neither `content_included`,
    `fragment` nor `next_action` is needed to discover continuation.
  - Each DOCX page remains an independent document. Do not concatenate XML roots and interpret the result as one XML document.
  - Stored IDs may expire or be evicted. Repeat the original read to regenerate a missing result.

### `offset`, `length`, and `next_offset`

- **Source**
  - Offset is zero-based and nonnegative; length is positive.
- **Default**
  - Requested chunk length: 8,000. Maximum requested length: 32,000, further bounded by reply budget.
  - These are host defaults. `tools/list` publishes the current maximum in the
    length schema and description and the current default/effective budgets in
    `x-doctokens-result-limits`; `get_runtime_info` returns the same values.
  - For complete retrieval, request the published maximum and let the host cap
    the reply; for a short excerpt, request only the needed character budget.
- **Processing**
  - Text uses Python Unicode characters; binary uses bytes. Fragments may split
    XML tags or JSON tokens. Their MIME type and selection are supplied initially,
    rather than repeated on every continuation.
  - Continue at the returned `next_offset`; offset 0 deliberately rereads the
    beginning. A continuation returns only text and next_offset, with native
    content_index replacing the text field over MCP. Binary fragments additionally
    identify Base64 encoding and byte units.
  - `next_offset=null` marks the end. Joining text chunks in offset order reproduces the complete stored text without normalization.
  - Binary fragments declare `encoding="base64"`; decode each fragment then join bytes. Bounds beyond the result end are rejected; an offset exactly at end returns an empty final fragment.
  - An omitted length is clamped to the configured maximum. Effective text length
    is at most `min(max_chunk_size, reply_chars)`. Effective binary length is at
    most `min(max_chunk_size, floor(reply_chars/4)*3)`, preserving Base64's four-character groups.

### Binary attachments

- **Output**
  - Original embedded bytes and a MIME type. External resources are not fetched.
- **Default**
  - At most 256 KiB inline for direct callers and supported MCP images; larger
    values use `result_id` and a resource URI.
- **Processing**
  - Prefer descriptor content type, then the package-part extension, then `application/octet-stream`.
  - MCP emits PNG/JPEG/WebP/GIF within the inline size cap as native image
    content. Other MIME types, including EMF and audio/video, return only a
    resource link regardless of size; binary data is not automatically embedded
    or Base64-expanded into the tool reply. Direct callers continue to receive
    `BinaryAttachment` objects within the cap.
  - Binary descriptors also return a `doctokens://result/<result_id>` URI. Large
    or non-displayable binary responses include an MCP resource link; an explicit
    resource read retrieves original bytes in one transfer. `read_result` remains available
    for bounded transfer. URI reads share the same byte-bounded storage, expiry
    and document lifetime; they never resolve arbitrary paths or download external targets.

### Errors

- **Output**
  - Stable `error.code` and explanatory `error.message`; MCP also sets `isError=true`.
  - Argument validation gives a concise message and up to eight field/message
    `details` records, without echoing submitted input values or a Pydantic traceback.
- **Codes**
  - `INVALID_ARGUMENT`, `UNKNOWN_TOOL`, `PATH_NOT_ALLOWED`, `DOCUMENT_NOT_FOUND`, `UNSUPPORTED_FORMAT`, `FORMAT_MISMATCH`.
  - `SOURCE_CHANGED`, `DOCUMENT_EXPIRED`, `RESULT_EXPIRED`, `DOCUMENT_TOO_LARGE`, `RESULT_TOO_LARGE`, `CAPACITY_EXCEEDED`.
  - `RESOURCE_NOT_FOUND`, `EXTERNAL_RESOURCE`, `OCR_UNAVAILABLE`, `INVALID_DOCUMENT`, `IO_ERROR`, `RUNTIME_CLOSED`, `INTERNAL_ERROR`.
  - Unexpected failures log to stderr; the response does not include a traceback.
