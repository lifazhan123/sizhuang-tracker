"""配置加载：config.yaml + 环境变量覆盖。

优先级：环境变量 > config.yaml > 内置默认值。
邮件相关敏感信息（授权码）建议只放在环境变量 / GitHub Secrets 中。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_NAME = "config.yaml"
EXAMPLE_CONFIG_NAME = "config.example.yaml"


def _env(name: str) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else None


def _env_bool(name: str) -> bool | None:
    v = _env(name)
    if v is None:
        return None
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_list(name: str) -> list[str] | None:
    v = _env(name)
    if v is None:
        return None
    return [x.strip() for x in v.replace(";", ",").split(",") if x.strip()]


# --------------------------------------------------------------------------- #
# 数据类
# --------------------------------------------------------------------------- #

@dataclass
class StockConfig:
    code: str = "002383"
    name: str = "合众思壮"
    market: int = 0  # 0=深市 1=沪市
    industry: str = ""

    @property
    def secid(self) -> str:
        """东方财富行情接口使用的 secid，如 0.002383。"""
        return f"{self.market}.{self.code}"

    @property
    def secucode(self) -> str:
        """带交易所后缀的代码，如 002383.SZ。"""
        suffix = {"0": "SZ", "1": "SH"}.get(str(self.market), "SZ")
        return f"{self.code}.{suffix}"


@dataclass
class ReportConfig:
    kline_days: int = 250
    fundflow_days: int = 60
    news_limit: int = 40
    news_days: int = 7              # 「近期资讯」时间窗口（天）
    news_history_days: int = 90     # 抓取池的回溯窗口（天）
    news_context_limit: int = 6     # 「近期重要公司事件」条数
    guba_limit: int = 40
    announce_limit: int = 15
    research_limit: int = 10
    output_dir: str = "output"


@dataclass
class MailConfig:
    enabled: bool = True
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465
    use_ssl: bool = True
    sender: str = ""
    password: str = ""
    recipients: list[str] = field(default_factory=list)
    subject_prefix: str = "[合众思壮·002383]"
    attach_markdown: bool = True

    def resolved_sender(self) -> str:
        return self.sender or _env("SZ_SMTP_USER") or ""


@dataclass
class IndexConfig:
    secid: str
    name: str


@dataclass
class AppConfig:
    stock: StockConfig
    report: ReportConfig
    mail: MailConfig
    market_index: list[IndexConfig] = field(default_factory=list)
    source_path: Path | None = None

    # -- 便捷方法 ---------------------------------------------------------- #
    def output_dir(self) -> Path:
        p = Path(self.report.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


# --------------------------------------------------------------------------- #
# 加载
# --------------------------------------------------------------------------- #

def _find_config(explicit: str | Path | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise FileNotFoundError(f"指定的配置文件不存在: {p}")
        return p

    candidates = [Path.cwd() / DEFAULT_CONFIG_NAME]
    here = Path(__file__).resolve()
    for parent in list(here.parents)[:5]:
        candidates.append(parent / DEFAULT_CONFIG_NAME)
        candidates.append(parent / EXAMPLE_CONFIG_NAME)

    for c in candidates:
        if c.exists():
            return c
    return None


def _deep_get(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load_config(path: str | Path | None = None) -> AppConfig:
    """读取配置。

    找不到配置文件时使用内置默认值（默认关注合众思壮 002383）。
    """
    cfg_path = _find_config(path)
    raw: dict[str, Any] = {}
    if cfg_path and cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    stock = StockConfig(
        code=str(_deep_get(raw, "stock", "code", default=StockConfig.code)),
        name=str(_deep_get(raw, "stock", "name", default=StockConfig.name)),
        market=int(_deep_get(raw, "stock", "market", default=StockConfig.market)),
        industry=str(_deep_get(raw, "stock", "industry", default="")),
    )

    rc = ReportConfig()
    report = ReportConfig(
        kline_days=int(_deep_get(raw, "report", "kline_days", default=rc.kline_days)),
        fundflow_days=int(_deep_get(raw, "report", "fundflow_days", default=rc.fundflow_days)),
        news_limit=int(_deep_get(raw, "report", "news_limit", default=rc.news_limit)),
        news_days=int(_deep_get(raw, "report", "news_days", default=rc.news_days)),
        news_history_days=int(_deep_get(raw, "report", "news_history_days", default=rc.news_history_days)),
        news_context_limit=int(_deep_get(raw, "report", "news_context_limit", default=rc.news_context_limit)),
        guba_limit=int(_deep_get(raw, "report", "guba_limit", default=rc.guba_limit)),
        announce_limit=int(_deep_get(raw, "report", "announce_limit", default=rc.announce_limit)),
        research_limit=int(_deep_get(raw, "report", "research_limit", default=rc.research_limit)),
        output_dir=str(_deep_get(raw, "report", "output_dir", default=rc.output_dir)),
    )

    mc = MailConfig()
    mail = MailConfig(
        enabled=_env_bool("SZ_MAIL_ENABLED")
        if _env_bool("SZ_MAIL_ENABLED") is not None
        else bool(_deep_get(raw, "mail", "enabled", default=mc.enabled)),
        smtp_host=_env("SZ_SMTP_HOST") or str(_deep_get(raw, "mail", "smtp_host", default=mc.smtp_host)),
        smtp_port=int(_env("SZ_SMTP_PORT") or _deep_get(raw, "mail", "smtp_port", default=mc.smtp_port)),
        use_ssl=bool(_deep_get(raw, "mail", "use_ssl", default=mc.use_ssl)),
        sender=_env("SZ_MAIL_FROM") or str(_deep_get(raw, "mail", "sender", default="")),
        password=_env("SZ_SMTP_PASSWORD") or str(_deep_get(raw, "mail", "password", default="")),
        recipients=_env_list("SZ_MAIL_TO")
        or list(_deep_get(raw, "mail", "recipients", default=[]) or []),
        subject_prefix=str(_deep_get(raw, "mail", "subject_prefix", default=mc.subject_prefix)),
        attach_markdown=bool(_deep_get(raw, "mail", "attach_markdown", default=mc.attach_markdown)),
    )

    idx_raw = raw.get("market_index") or []
    market_index = [
        IndexConfig(secid=str(i.get("secid")), name=str(i.get("name", i.get("secid"))))
        for i in idx_raw
        if isinstance(i, dict) and i.get("secid")
    ]
    if not market_index:
        market_index = [
            IndexConfig("1.000001", "上证指数"),
            IndexConfig("0.399001", "深证成指"),
            IndexConfig("0.399006", "创业板指"),
        ]

    return AppConfig(
        stock=stock,
        report=report,
        mail=mail,
        market_index=market_index,
        source_path=cfg_path,
    )
