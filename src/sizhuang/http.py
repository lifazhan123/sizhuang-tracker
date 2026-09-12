"""统一的 HTTP 客户端。

东方财富的部分域名（尤其 push2.eastmoney.com）在高峰期会偶发
ProxyError / RemoteDisconnected，这里做三件事：
  1. 会话复用 + 浏览器 UA + 合理 Referer
  2. 多域名回落（同一接口在多个镜像域名上可用）
  3. 指数退避重试
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any, Callable, Iterable, Mapping

import requests

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, text/plain, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

# 行情主站的镜像域名（按顺序回落）
# 注意：push2delay 是延时行情源，稳定性最好，放在最后兜底。
QUOTE_HOSTS = [
    "push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "1.push2.eastmoney.com",
    "push2delay.eastmoney.com",
]

# K线历史接口的镜像域名。该域名限流较严，失败时由调用方回落到腾讯/新浪。
KLINE_HOSTS = [
    "push2his.eastmoney.com",
    "63.push2his.eastmoney.com",
    "push2delay.eastmoney.com",
]

# 资金流向接口。push2his 提供完整历史；push2delay 只能取到最新 1 天，仅作兜底。
FFLOW_HOSTS = [
    "push2his.eastmoney.com",
    "63.push2his.eastmoney.com",
    "push2delay.eastmoney.com",
]


class HttpClient:
    """带重试与镜像回落的轻量 HTTP 客户端。"""

    def __init__(
        self,
        timeout: float = 15.0,
        retries: int = 3,
        backoff: float = 1.5,
        min_interval: float = 0.35,
        referer: str = "https://quote.eastmoney.com/",
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.min_interval = min_interval
        self.referer = referer
        self._session = requests.Session()
        self._last_call = 0.0

    # -- 内部 ------------------------------------------------------------- #
    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        h = dict(DEFAULT_HEADERS)
        h["User-Agent"] = random.choice(USER_AGENTS)
        h["Referer"] = self.referer
        if extra:
            h.update(extra)
        return h

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    # -- 对外 ------------------------------------------------------------- #
    def get_text(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        retries: int | None = None,
    ) -> str | None:
        n = retries if retries is not None else self.retries
        last_err: Exception | None = None
        for attempt in range(1, n + 1):
            self._throttle()
            try:
                resp = self._session.get(
                    url, params=params, headers=self._headers(headers), timeout=self.timeout
                )
                if resp.status_code == 200 and resp.text:
                    resp.encoding = resp.encoding or "utf-8"
                    return resp.text
                last_err = RuntimeError(f"HTTP {resp.status_code}")
            except Exception as exc:  # noqa: BLE001 - 网络层统一降级处理
                last_err = exc
            if attempt < n:
                time.sleep(self.backoff * attempt + random.uniform(0, 0.4))
        log.warning("GET 失败 url=%s err=%s", url, last_err)
        return None

    def post_text(
        self,
        url: str,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        retries: int | None = None,
    ) -> str | None:
        n = retries if retries is not None else self.retries
        last_err: Exception | None = None
        for attempt in range(1, n + 1):
            self._throttle()
            try:
                resp = self._session.post(
                    url, data=data, headers=self._headers(headers), timeout=self.timeout
                )
                if resp.status_code == 200:
                    return resp.text
                last_err = RuntimeError(f"HTTP {resp.status_code}")
            except Exception as exc:  # noqa: BLE001
                last_err = exc
            if attempt < n:
                time.sleep(self.backoff * attempt)
        log.warning("POST 失败 url=%s err=%s", url, last_err)
        return None

    def get_json(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        retries: int | None = None,
    ) -> Any | None:
        txt = self.get_text(url, params=params, headers=headers, retries=retries)
        if txt is None:
            return None
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            log.warning("JSON 解析失败 url=%s head=%s", url, txt[:120])
            return None

    def get_json_with_hosts(
        self,
        hosts: Iterable[str],
        path: str,
        params: Mapping[str, Any] | None = None,
        scheme: str = "https",
        headers: Mapping[str, str] | None = None,
        retries_per_host: int = 2,
        validator: Callable[[Any], bool] | None = None,
    ) -> Any | None:
        """对同一接口轮询多个镜像域名，任一成功即返回。

        validator 用于剔除「HTTP 200 但业务数据为空」的响应
        （例如 push2delay 对 K 线接口会返回 `klines: []`）。
        """
        for host in hosts:
            data = self.get_json(
                f"{scheme}://{host}{path}",
                params=params,
                headers=headers,
                retries=retries_per_host,
            )
            if data is None:
                continue
            if validator is not None and not validator(data):
                log.debug("镜像 %s 返回空数据，尝试下一个", host)
                continue
            return data
        return None

    def get_text_with_hosts(
        self,
        hosts: Iterable[str],
        path: str,
        params: Mapping[str, Any] | None = None,
        scheme: str = "https",
        headers: Mapping[str, str] | None = None,
        retries_per_host: int = 2,
        validator: Callable[[str], bool] | None = None,
    ) -> str | None:
        for host in hosts:
            txt = self.get_text(
                f"{scheme}://{host}{path}",
                params=params,
                headers=headers,
                retries=retries_per_host,
            )
            if not txt:
                continue
            if validator is not None and not validator(txt):
                continue
            return txt
        return None

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# 解析工具
# --------------------------------------------------------------------------- #

_JSONP_RE = re.compile(r"^[^(]*\((.*)\)[;\s]*$", re.S)


def parse_jsonp(text: str | None) -> Any | None:
    """解析 JSONP / 带回调包装的响应。"""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSONP_RE.match(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def parse_html_json_var(html: str | None, var_name: str) -> Any | None:
    """从 HTML 中提取 `var xxx={...}` 形式的内嵌 JSON 对象。

    东方财富股吧列表页把帖子数据以 `var article_list={...}` 内联在页面里，
    这里用 raw_decode 做括号配对解析，比正则更稳。
    """
    if not html:
        return None
    marker = f"{var_name}="
    idx = html.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:].lstrip())
        return obj
    except json.JSONDecodeError:
        return None


def to_float(v: Any, default: float | None = None) -> float | None:
    """东方财富接口常用 '-' 表示无数据。"""
    if v is None or v == "-" or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
