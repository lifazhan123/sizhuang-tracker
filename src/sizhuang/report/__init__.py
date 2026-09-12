"""报告层：把数据包渲染成 Markdown 与 HTML（邮件正文）。"""

from __future__ import annotations

from .render import render_html, render_markdown, save_reports  # noqa: F401

__all__ = ["render_markdown", "render_html", "save_reports"]
