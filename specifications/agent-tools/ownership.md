# Ownership and limits

[Agent tools](README.md) / Ownership

## Fields

### Snapshot identity

- **Processing**
  - First access copies the local file into a runtime-owned temporary snapshot while calculating its SHA-256 revision.
  - File size, nanosecond modification time, and creation/change time are checked before and after copying. A concurrent change rejects the snapshot.
  - Path reuse checks that stat fingerprint plus normalized parser options. A different fingerprint creates a new snapshot. The stat check is a cache freshness check, not cryptographic change detection for an adversarially restored timestamp.
  - Existing document IDs remain pinned to their original bytes until expiration, eviction, or release.
  - Format parsers continue to own OPC limits; the adapter never extracts ZIP members to the filesystem or downloads external targets.

### Sessions

- **Default**
  - At most 4 open sessions; 600 seconds idle lifetime.
  - `max_session_memory_bytes=268435456` (256 MiB) per session and
    `max_session_total_memory_bytes=536870912` (512 MiB) across resident sessions.
- **Processing**
  - DOCX/PPTX body, navigation and searches reuse explicit sessions. XLSX ordinary
    reads, searches and queries use scoped source operations unless a full session
    already exists. The lightweight XLSX directory and original-image path do not
    require cells. Explicit full inspection and detailed resource rendering can
    establish a full XLSX session.
  - Evict the least recently used inactive session before admitting another. Snapshot identity survives session eviction; reopening uses the same bytes and options.
  - Validate package metadata before full parsing. Reserve `1 MiB + 1024 * entry
    count + 2 * total XML/rels bytes + 12 * largest XML/rels part bytes + min(other
    part bytes, 8 MiB)`. Unused XML contributes to this conservative reservation.
    The largest-part allowance estimates transient tree expansion without treating
    every disposable slide tree as simultaneously resident.
  - Reject a reservation larger than either configured memory limit without opening
    a session. Otherwise evict inactive sessions until both count and total memory
    allow admission. Active leases are protected.
  - Check growth at worksheet rows, DOCX body blocks and PPTX slides. XLSX charges
    128 bytes per row plus 640 bytes per retained cell and four bytes per character
    in ref/text/raw/formula; it does not recursively inspect every cell. DOCX/PPTX
    measure completed fragments and the final parsed value, following value
    containers/dataclasses and counting shared identities once per measurement.
    The estimate is the larger of reservation and measured/counted growth.
  - A growing parse receives at most the per-session limit and the currently
    unreserved total capacity. If growth exhausts aggregate capacity and inactive
    owners remain, reclaim them and retry once with the larger allowance. Never
    commit a half-open session. A remaining excess returns `SESSION_MEMORY_LIMIT`;
    it does not silently narrow the requested operation.
  - Eviction closes the parser and releases its reservation; snapshot and stored
    result identities survive. Release, expiry and runtime exit also clear the
    session estimate. `get_runtime_info` exposes `session_estimated_bytes`, both
    `session_memory_limits` and `mcp_output_mode` only on explicit inspection.
  - Runtime locking and active leases protect operations from maintenance or eviction. Explicit release and runtime exit close readers and remove snapshots.
  - Background maintenance runs at most every 30 seconds; expiration also runs
    before tool calls. Estimates are admission heuristics, not process RSS or a
    hard allocation bound. They exclude unrelated runtime state, rendering/query
    temporaries, external OCR providers and allocator retention after release.
    Scoped operations do not reserve full sessions. Full parsing is not streaming
    parsing. Both limits are host configuration and have corresponding CLI flags.

### Documents and snapshots

- **Default**
  - 32 snapshots; 128 MiB per source file; 512 MiB total snapshot bytes.
- **Processing**
  - Evict inactive snapshots by last access before admission. Associated results are invalidated by the next cleanup/call.
  - Limits are configurable through `RuntimeConfig`; the corresponding CLI limits are listed by `doctokens-mcp --help`.

### Results

- **Default**
  - 64 MiB stored results, 600 seconds idle lifetime.
- **Processing**
  - Account UTF-8 text or binary bytes, serialized metadata, and a per-entry overhead allowance. Evict least recently used results until the new value fits.
  - Oversize selections that require storage fail explicitly; no content is silently truncated. Small inline results can be returned without caching when storage capacity is too small.
  - A response's part IDs are protected while its metadata is admitted. If the complete response cannot fit, return `RESULT_TOO_LARGE` rather than references evicted by that same call.
  - Retrieval refreshes result and document idle lifetime. Release removes all results belonging to that document.

### Runtime

- **Processing**
  - All caches belong to a `ToolRuntime` instance. Parser packages contain no cross-request cache.
  - Default asynchronous worker count is 2. A runtime serializes parser access under its lock; async calls move work off the event loop rather than promise parallel parsing. Closing rejects future calls, releases owned objects, and waits for workers and maintenance to exit.
