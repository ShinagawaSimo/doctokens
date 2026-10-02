"""Office tools with a shared runtime for direct calls and optional MCP."""

from .config import RuntimeConfig
from .models import BinaryAttachment, ToolDefinition, ToolResponse
from .runtime import ToolRuntime

__version__ = "0.1.0"

__all__ = ["BinaryAttachment", "RuntimeConfig", "ToolDefinition", "ToolResponse", "ToolRuntime"]
