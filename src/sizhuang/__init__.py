"""合众思壮(002383) 个股观察与每日新闻推送工程。

模块划分：
    fetchers/  数据抓取层（东方财富行情/资金/新闻/公告/研报/股吧 等）
    analysis/  分析层（技术指标、趋势研判、舆情情绪）
    report/    报告层（Markdown + HTML 渲染）
    notify/    通知层（SMTP 邮件推送）
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
