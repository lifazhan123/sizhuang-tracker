"""抓取器基类与公共上下文。"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import AppConfig
from ..http import HttpClient


class FetchError(RuntimeError):
    """抓取失败（网络异常、接口改版、返回空数据等）。"""


@dataclass
class FetchContext:
    """一次运行共享的配置与 HTTP 会话。"""
    config: AppConfig
    client: HttpClient

    @property
    def stock(self):
        return self.config.stock

    @property
    def report(self):
        return self.config.report


class Fetcher:
    """所有抓取器的基类，统一持有上下文。"""

    name: str = "fetcher"

    def __init__(self, ctx: FetchContext) -> None:
        self.ctx = ctx
        self.client = ctx.client

    # 子类实现
    def fetch(self, *args, **kwargs):  # pragma: no cover - 抽象
        raise NotImplementedError
