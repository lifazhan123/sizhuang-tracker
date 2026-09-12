"""数据抓取层。

各模块只依赖 `HttpClient` 与 `StockConfig`，返回 `models` 中的数据结构。
单个抓取器失败不应中断整体流程——统一抛 `FetchError`，由编排层收集到
`DailyBundle.errors` 中，报告里以「数据缺口」方式提示。
"""

from __future__ import annotations

from .base import FetchError, Fetcher, FetchContext  # noqa: F401

__all__ = ["FetchError", "Fetcher", "FetchContext"]
