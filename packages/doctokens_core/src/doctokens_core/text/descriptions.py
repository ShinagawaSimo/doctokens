"""Choose readable saved descriptions without fabricating source text."""


def first_readable(*values: str | None) -> str | None:
    """Skip whitespace-only candidates while preserving meaningful spacing."""
    return next((value for value in values if value is not None and value.strip()), None)
