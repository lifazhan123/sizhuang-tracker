"""通知层：SMTP 邮件推送。"""

from __future__ import annotations

from .mailer import MailError, send_report  # noqa: F401

__all__ = ["MailError", "send_report"]
