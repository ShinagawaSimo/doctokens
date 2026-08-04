"""最终面向大模型的输出渲染器。"""

from .html5 import iter_html5, to_html5, write_outputs

__all__ = [
    "iter_html5",
    "to_html5",
    "write_outputs",
]
