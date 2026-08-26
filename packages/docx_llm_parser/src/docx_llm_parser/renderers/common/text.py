"""Text processing logic shared across density renderers.

Run merging, signature computation, and format filtering are pure data
transformations that do not depend on specific output tag syntax."""

from __future__ import annotations

from ...core.models import Run, RunFormat

RunSignature = tuple[
    object,
    tuple[tuple[str, str], ...],
    tuple[tuple[str, bool | str | None], ...],
    tuple[tuple[str, object], ...],
    tuple[tuple[str, object], ...],
]


def merge_text_runs(runs: list[Run]) -> list[Run]:
    """Merge adjacent plain-text runs with the same output semantics, reducing fragmentation in the final output."""
    merged: list[Run] = []
    pending: Run | None = None
    pending_key: RunSignature | None = None

    for run in runs:
        # Page-break sentinels are layout boundaries, never visible text.
        if run.get("pageBreak"):
            if pending is not None:
                merged.append(pending)
                pending = None
                pending_key = None
            continue
        # Runs containing inline objects are not merged; they are added to the result directly.
        if "objects" in run:
            if pending is not None:
                merged.append(pending)
                pending = None
                pending_key = None
            merged.append(run)
            continue

        text = run["text"]
        if not text:
            continue
        signature = run_output_signature(run)
        if pending is not None and pending_key == signature:
            pending["text"] += text
            continue
        if pending is not None:
            merged.append(pending)
        pending = {"text": text}
        if "revision" in run:
            pending["revision"] = run["revision"]
        if "revisionAuthor" in run:
            pending["revisionAuthor"] = run["revisionAuthor"]
        if "revisionDate" in run:
            pending["revisionDate"] = run["revisionDate"]
        if "link" in run:
            pending["link"] = run["link"]
        if "field" in run:
            pending["field"] = run["field"]
        if "contentControls" in run:
            pending["contentControls"] = run["contentControls"]
        if "format" in run:
            pending["format"] = run["format"]
        pending_key = signature

    if pending is not None:
        merged.append(pending)
    return merged


def split_runs_at_page_breaks(runs: list[Run]) -> list[list[Run]]:
    """Split an inline run stream at calculated page-break sentinels."""
    segments: list[list[Run]] = [[]]
    for run in runs:
        if run.get("pageBreak"):
            segments.append([])
        else:
            segments[-1].append(run)
    return segments


def run_output_signature(run: Run) -> RunSignature:
    """Generate a stable signature of a run's output-relevant fields, used to decide whether adjacent runs can be merged."""
    link: tuple[tuple[str, str], ...] = ()
    if "link" in run:
        link_items: list[tuple[str, str]] = []
        if "href" in run["link"]:
            link_items.append(("href", run["link"]["href"]))
        if "anchor" in run["link"]:
            link_items.append(("anchor", run["link"]["anchor"]))
        link = tuple(sorted(link_items))
    fmt = tuple(sorted((run.get("format") or {}).items()))
    field = tuple(sorted((run.get("field") or {}).items()))
    controls = tuple(
        (
            control.get("controlType", ""),
            control.get("id", ""),
            control.get("tag", ""),
            control.get("alias", ""),
        )
        for control in run.get("contentControls", [])
    )
    return (run.get("revision"), link, fmt, field, (("contentControls", controls),) if controls else ())


def filter_format(run: Run) -> RunFormat:
    """Filter run formats, removing the default hyperlink style (blue + underline) to avoid output noise."""
    fmt = dict(run.get("format") or {})
    if run.get("link"):
        if fmt.get("color") in {"#0563C1", "#0000FF"}:
            fmt.pop("color", None)
        if fmt.get("underline") is True:
            fmt.pop("underline", None)
    return fmt
