"""命令行入口。

用法：
    python -m sizhuang.cli run                  # 抓取 → 生成报告 → 发送邮件
    python -m sizhuang.cli run --no-mail        # 只生成报告，不发邮件
    python -m sizhuang.cli run --preview        # 生成后在终端打印 Markdown
    python -m sizhuang.cli check                # 检查配置与数据源连通性
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 允许直接以脚本方式运行
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sizhuang.analysis.trend import analyze_trend  # type: ignore
    from sizhuang.config import load_config  # type: ignore
    from sizhuang.logging_setup import setup_logging  # type: ignore
    from sizhuang.notify import MailError, send_report  # type: ignore
    from sizhuang.pipeline import collect  # type: ignore
    from sizhuang.report import render_html, render_markdown, save_reports  # type: ignore
else:
    from .analysis.trend import analyze_trend
    from .config import load_config
    from .logging_setup import setup_logging
    from .notify import MailError, send_report
    from .pipeline import collect
    from .report import render_html, render_markdown, save_reports

EXIT_OK = 0
EXIT_FETCH_FAILED = 2
EXIT_MAIL_FAILED = 3


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sizhuang",
        description="合众思壮(002383) 个股观察与每日新闻邮件推送",
    )
    p.add_argument("-c", "--config", default=None, help="配置文件路径（默认自动查找 config.yaml）")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="执行一次完整流程")
    run.add_argument("--no-mail", action="store_true", help="跳过邮件发送")
    run.add_argument("--preview", action="store_true", help="在终端打印 Markdown 报告")
    run.add_argument("--json", dest="dump_json", action="store_true", help="额外导出原始数据 JSON")
    run.add_argument("--out", default=None, help="报告输出目录（覆盖配置）")

    chk = sub.add_parser("check", help="检查配置与各数据源连通性")
    chk.add_argument("--json", dest="dump_json", action="store_true", help="以 JSON 输出检查结果")

    return p


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    if args.out:
        cfg.report.output_dir = args.out

    print(f"→ 目标：{cfg.stock.name}（{cfg.stock.code}）  secid={cfg.stock.secid}")
    bundle, trend = collect(cfg)

    if not bundle.kline.bars:
        print("✗ 未能获取K线数据，流程终止。请检查网络或稍后重试。", file=sys.stderr)
        if bundle.errors:
            print("  失败明细：" + "；".join(bundle.errors), file=sys.stderr)
        return EXIT_FETCH_FAILED

    subject = (f"{cfg.mail.subject_prefix} {cfg.stock.name} 每日观察报告 "
               f"{bundle.trade_date}（{trend.label} {trend.score}:{100 - trend.score}）")

    md_path, html_path = save_reports(bundle, trend, cfg.report.output_dir, subject)
    print(f"✓ 报告已生成：{md_path.name} / {html_path.name}")

    if args.dump_json:
        jp = Path(cfg.report.output_dir) / f"{cfg.stock.code}_{bundle.trade_date}_raw.json"
        jp.write_text(json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ 原始数据已导出：{jp.name}")

    if args.preview:
        print("\n" + "=" * 78)
        print(render_markdown(bundle, trend))
        print("=" * 78 + "\n")

    code = EXIT_OK
    if args.no_mail:
        print("· 已按 --no-mail 跳过邮件发送")
    else:
        try:
            send_report(
                cfg.mail,
                subject=subject,
                html_body=render_html(bundle, trend, subject),
                text_body=render_markdown(bundle, trend),
                attachments=[md_path] if cfg.mail.attach_markdown else None,
            )
            print(f"✓ 邮件已发送：{'、'.join(cfg.mail.recipients)}")
        except MailError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            code = EXIT_MAIL_FAILED

    if bundle.errors:
        print(f"⚠ 本期数据缺口 {len(bundle.errors)} 项：" + "；".join(bundle.errors))
    return code


def cmd_check(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    from .fetchers.announcement import AnnouncementFetcher
    from .fetchers.fundamental import FundamentalFetcher
    from .fetchers.fundflow import FundFlowFetcher, MarginFetcher
    from .fetchers.guba import GubaFetcher
    from .fetchers.news import NewsFetcher
    from .fetchers.quote import IndexFetcher, KlineFetcher, QuoteFetcher
    from .fetchers.research import ResearchFetcher
    from .pipeline import build_context

    ctx = build_context(cfg)
    checks = [
        ("实时行情", lambda: QuoteFetcher(ctx).fetch()),
        ("K线", lambda: KlineFetcher(ctx).fetch()),
        ("资金流向", lambda: FundFlowFetcher(ctx).fetch()),
        ("融资融券", lambda: MarginFetcher(ctx).fetch()),
        ("财务指标", lambda: FundamentalFetcher(ctx).fetch()),
        ("全网新闻", lambda: NewsFetcher(ctx).fetch()),
        ("公司公告", lambda: AnnouncementFetcher(ctx).fetch()),
        ("机构研报", lambda: ResearchFetcher(ctx).fetch()),
        ("股吧帖子", lambda: GubaFetcher(ctx).fetch()),
        ("大盘指数", lambda: IndexFetcher(ctx).fetch()),
    ]
    result: dict[str, str] = {}
    print(f"配置来源：{cfg.source_path or '（内置默认值）'}")
    print(f"目标股票：{cfg.stock.name}（{cfg.stock.code}）")
    print("-" * 60)
    for name, fn in checks:
        try:
            val = fn()
            n = len(val) if isinstance(val, list) else (len(val.days) if hasattr(val, "days") else 1)
            result[name] = f"OK ({n})"
        except Exception as exc:  # noqa: BLE001
            result[name] = f"FAIL: {type(exc).__name__}"
        print(f"{name:<10} {result[name]}")

    mail_ok = "未配置"
    if cfg.mail.recipients and cfg.mail.resolved_sender() and cfg.mail.password:
        mail_ok = f"已配置 → {'、'.join(cfg.mail.recipients)}"
    elif not cfg.mail.enabled:
        mail_ok = "已关闭 (enabled=false)"
    print(f"{'邮件配置':<10} {mail_ok}")
    ctx.client.close()

    if args.dump_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "check":
        return cmd_check(args)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
