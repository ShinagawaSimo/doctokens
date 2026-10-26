# Compound File Binary access

[COMMON](README.md) / CFB

`doctokens_core.containers.cfb` provides bounded, read-only CFB version 3 access. It does
not interpret BIFF records or activate OLE objects.

## Reader and streams

### `CfbReader(source, limits=None)`

- **Source**
  - A path or immutable `bytes`; MS-CFB header, allocation tables and directory.
- **Output**
  - An explicit context-managed owner. Enter once and close on exit or failure.
  - `has_root_stream(name)` queries root-owned stream identity.
  - `open_root_stream(name)` returns an exact logical stream view.
- **Parsing**
  - Accept version 3, little-endian, 512-byte ordinary sectors, 64-byte mini
    sectors and the 4096-byte mini-stream cutoff. Version 4 is explicitly unsupported.
  - Read header and extended DIFAT references, then decode FAT and MiniFAT pages
    directly into packed 32-bit unsigned arrays. Reject other native element
    widths and byte-swap on big-endian hosts. Validate counts, markers and bounds.
  - Traverse the root's sibling tree iteratively. Reject cycles, duplicate root
    names and invalid entries. Do not enter child storages or flatten embedded streams.
  - Read only required directory pages; retain at most eight pages.
  - Bound chain length and reject repeated sectors and overlaps among visited
    allocation structures and ordinary streams. Unvisited embedded streams are
    not audited. Mini-chain validation is local to the requested stream.
  - Ignore the directory size high word in version 3, as recommended by MS-CFB.
- **Diagnostics**
  - Invalid container or configured limit: `CfbError`.
  - Unsupported container version or native integer-array width:
    `CfbUnsupportedError`, a `CfbError` subclass.
  - Use before enter, after close or a second entry: `RuntimeError`.

### `CfbStream.read_at(offset, size)`

- **Output**
  - Exactly `size` bytes; never expose bytes beyond the declared logical length.
- **Parsing**
  - Validate the chain at open time without assembling its complete payload.
    Reuse a root stream's validated chain within the same reader; each open returns
    a separate view. Release retained indexes when the reader closes.
  - Map ordinary positions through `(sector_id + 1) * 512 + within_sector`.
  - Coalesce physical runs covered by the request.
  - Load MiniFAT only for a requested nonempty stream shorter than 4096 bytes.
    Map its 64-byte mini sectors through the root Mini Stream's ordinary chain.
    Keep the root Mini Stream as a view, not a complete payload copy.
  - A stream shares the reader's lifetime and fails after its source is closed.
- **Diagnostics**
  - Negative or out-of-range reads and short physical reads: `CfbError`.

## Limits

### `CfbLimits`

- **Defaults**
  - `max_file_bytes = 268435456`.
  - `max_stream_bytes = 134217728`, also applied to the root Mini Stream when used.
  - `max_directory_entries = 32768`.
- **Parsing**
  - Positive integers only; reject booleans.
  - Check limits before associated allocations. Actual file sectors bound chains
    and allocation-table indexes. Execution checkpoints permit cooperative cancellation.
  - Limits constrain inputs and structures; they are not process RSS guarantees.
- **Diagnostics**
  - Invalid limit argument: `ValueError`.

## References

- [MS-CFB](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/):
  sections 2.1–2.6.
