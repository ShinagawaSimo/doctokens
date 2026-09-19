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
    """Merge adjacent runs with identical output semantics."""
    merged_runs: list[Run] = []
    pending_run: Run | None = None
    pending_signature: RunSignature | None = None

    for run in runs:
        # Page-break sentinels are layout boundaries, never visible text.
        if run.get("pageBreak"):
            if pending_run is not None:
                merged_runs.append(pending_run)
                pending_run = None
                pending_signature = None
            continue
        # Runs containing inline objects are not merged; they are added to the result directly.
        if "objects" in run:
            if pending_run is not None:
                merged_runs.append(pending_run)
                pending_run = None
                pending_signature = None
            merged_runs.append(run)
            continue

        run_text = run["text"]
        if not run_text:
            continue
        signature = run_output_signature(run)
        if pending_run is not None and pending_signature == signature:
            pending_run["text"] += run_text
            continue
        if pending_run is not None:
            merged_runs.append(pending_run)
        pending_run = {"text": run_text}
        if "revision" in run:
            pending_run["revision"] = run["revision"]
        if "revisionAuthor" in run:
            pending_run["revisionAuthor"] = run["revisionAuthor"]
        if "revisionDate" in run:
            pending_run["revisionDate"] = run["revisionDate"]
        if "link" in run:
            pending_run["link"] = run["link"]
        if "field" in run:
            pending_run["field"] = run["field"]
        if "contentControls" in run:
            pending_run["contentControls"] = run["contentControls"]
        if "format" in run:
            pending_run["format"] = run["format"]
        pending_signature = signature

    if pending_run is not None:
        merged_runs.append(pending_run)
    return merged_runs


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
    run_format = tuple(sorted((run.get("format") or {}).items()))
    field_data = tuple(sorted((run.get("field") or {}).items()))
    control_signature = tuple(
        (
            control.get("controlType", ""),
            control.get("id", ""),
            control.get("tag", ""),
            control.get("alias", ""),
        )
        for control in run.get("contentControls", [])
    )
    return (
        run.get("revision"),
        link,
        run_format,
        field_data,
        (("contentControls", control_signature),) if control_signature else (),
    )


def filter_format(run: Run) -> RunFormat:
    """Filter run formats, removing the default hyperlink style (blue + underline) to avoid output noise."""
    run_format = dict(run.get("format") or {})
    if run.get("link"):
        if run_format.get("color") in {"#0563C1", "#0000FF"}:
            run_format.pop("color", None)
        if run_format.get("underline") is True:
            run_format.pop("underline", None)
    return run_format
