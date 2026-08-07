"""图表和 SmartArt 的 inline 渲染与 resource 渲染辅助。"""

from .charts import chart_to_html5, chart_type_attrs, render_chart_resource
from .smartarts import render_smartart_resource, smartart_to_html5

__all__ = [
    "chart_to_html5",
    "chart_type_attrs",
    "render_chart_resource",
    "render_smartart_resource",
    "smartart_to_html5",
]
