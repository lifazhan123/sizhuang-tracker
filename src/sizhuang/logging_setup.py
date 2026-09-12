"""统一日志配置：控制台 + 可选文件。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONFIGURED = False


def _force_utf8_stdio() -> None:
    """Windows 控制台默认 GBK，中文日志会乱码；统一切到 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, OSError, ValueError):
            pass


def setup_logging(level: str = "INFO", log_file: str | Path | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    _force_utf8_stdio()

    fmt = "%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s"
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    root.addHandler(sh)

    if log_file:
        p = Path(log_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(p, encoding="utf-8")
        fh.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        root.addHandler(fh)

    # 第三方库降噪
    for noisy in ("urllib3", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
