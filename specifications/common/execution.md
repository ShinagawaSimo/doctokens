# Execution control

[COMMON](README.md) / Execution control

## Fields

### `ParseControl`

- **Source**
  - `doctokens_core.execution.ParseControl(progress=None)`; caller-owned state.
- **Processing**
  - `cancel()` sets a thread-safe event. `check(stage="reading")` raises
    `ParseCancelled` if cancelled. Otherwise an optional `(sequence, stage)`
    callback receives monotonically increasing phase updates at most once per
    250 ms. The sequence is not a percentage or completed-work estimate.
  - Direct ToolRuntime execute/aexecute accept `control=`. Async cancellation
    signals its control even if the executor thread has already started.

### `parse_scope`

- **Source**
  - `with parse_scope(control): ...`, imported from doctokens_core.execution.
- **Processing**
  - Binds control to the current execution context, resets it on exit and never
    caches document data. Parsers without a scope retain their ordinary behavior.
  - Checkpoints cover package byte reads, format units, text/query processing,
    selected rendering loops and runtime result admission. Cooperative checks
    cannot interrupt an arbitrary external provider, Python sort or native call
    in the middle. No hard cancellation-latency bound is promised.

### `ParseCancelled`

- **Diagnostics**
  - Derives from BaseException so optional-content recovery does not swallow
    cancellation as a parse warning. Explicit sessions close on failed entry;
    runtime calls map the exception to CANCELLED while cancelled async callers
    keep their native asyncio cancellation. A caller using parse_scope directly
    must unwind its owned context managers or close resumable readers.
