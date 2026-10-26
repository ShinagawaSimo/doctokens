"""pptx namespaces."""

from __future__ import annotations

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"


# 1x1 transparent PNG (base64).
PNG_BYTES = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


_PRESENTATION_OVERRIDE = (
    '<Override PartName="/ppt/presentation.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
)


P15_NS = "http://schemas.microsoft.com/office/powerpoint/2012/main"
