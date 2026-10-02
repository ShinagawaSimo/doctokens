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
- **Processing**
  - DOCX/PPTX body and navigation reuse explicit sessions. XLSX search/query/resource operations establish full sessions on demand.
  - Evict the least recently used inactive session before admitting another. Snapshot identity survives session eviction; reopening uses the same bytes and options.
  - Runtime locking and active leases protect operations from maintenance or eviction. Explicit release and runtime exit close readers and remove snapshots.
  - Background maintenance runs at most every 30 seconds; expiration also runs before tool calls. Count limits bound retained sessions, not parser peak RSS. Full parsing is not streaming parsing.

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
