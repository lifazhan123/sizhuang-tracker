"""SMTP 邮件推送。

支持两种加密方式：
  - SSL   （端口 465，QQ/163 常用）
  - STARTTLS（端口 587，Gmail/Outlook 常用）
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from ..config import MailConfig

log = logging.getLogger(__name__)


class MailError(RuntimeError):
    """邮件发送失败。"""


def _validate(cfg: MailConfig) -> None:
    missing = []
    if not cfg.smtp_host:
        missing.append("smtp_host")
    if not cfg.resolved_sender():
        missing.append("sender / SZ_SMTP_USER / SZ_MAIL_FROM")
    if not cfg.password:
        missing.append("password / SZ_SMTP_PASSWORD（注意是邮箱授权码，不是登录密码）")
    if not cfg.recipients:
        missing.append("recipients / SZ_MAIL_TO")
    if missing:
        raise MailError("邮件配置不完整，缺少：" + "、".join(missing))


def send_report(
    cfg: MailConfig,
    subject: str,
    html_body: str,
    text_body: str = "",
    attachments: list[Path] | None = None,
) -> None:
    """发送一封 HTML 邮件（可选附带 Markdown 报告）。"""
    if not cfg.enabled:
        log.info("邮件推送已关闭（mail.enabled=false），跳过发送")
        return

    _validate(cfg)

    sender = cfg.resolved_sender()
    msg = MIMEMultipart("mixed")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("股票观察助手", "utf-8")), sender))
    msg["To"] = ", ".join(cfg.recipients)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1] or "localhost")

    alt = MIMEMultipart("alternative")
    if text_body:
        alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    for path in attachments or []:
        p = Path(path)
        if not p.exists():
            continue
        part = MIMEText(p.read_text(encoding="utf-8"), "plain", "utf-8")
        part.add_header("Content-Disposition", "attachment",
                        filename=("utf-8", "", p.name))
        msg.attach(part)

    context = ssl.create_default_context()
    try:
        if cfg.use_ssl:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=30, context=context) as srv:
                srv.login(sender, cfg.password)
                srv.sendmail(sender, cfg.recipients, msg.as_string())
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as srv:
                srv.ehlo()
                srv.starttls(context=context)
                srv.ehlo()
                srv.login(sender, cfg.password)
                srv.sendmail(sender, cfg.recipients, msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError(
            f"SMTP 认证失败（{exc.smtp_code}）：请确认使用的是邮箱『授权码』而非登录密码；"
            "QQ邮箱需在 设置→账户 中开启 SMTP 服务并生成授权码。"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - 统一转成可读错误
        raise MailError(f"邮件发送失败：{type(exc).__name__}: {exc}") from exc

    log.info("邮件已发送至 %s", "、".join(cfg.recipients))
