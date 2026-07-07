"""日志脱敏工具。"""

from __future__ import annotations

import logging
import re
from typing import Any


SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(access_token|refresh_token|token|api[_-]?key|secret|password|cookie)(['\"\s:=]+)([^'\"\s,&]+)"),
    re.compile(r"(?i)(access_key_secret|client_secret|app_secret)(['\"\s:=]+)([^'\"\s,&]+)"),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"(?i)(transaction_id|out_trade_no|prepay_id)(['\"\s:=]+)([^'\"\s,&]+)"),
]


def mask_sensitive_data(value: Any) -> str:
    """对常见凭据、手机号、支付号做保守脱敏。"""
    text = str(value)
    text = SENSITIVE_PATTERNS[0].sub(r"\1***", text)
    for pattern in SENSITIVE_PATTERNS[1:3]:
        text = pattern.sub(r"\1\2***", text)
    text = SENSITIVE_PATTERNS[3].sub(lambda m: f"{m.group(0)[:3]}****{m.group(0)[-4:]}", text)
    text = SENSITIVE_PATTERNS[4].sub(r"\1\2***", text)
    return text


class SensitiveDataFilter(logging.Filter):
    """在日志写出前尽量消除敏感值。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {key: mask_sensitive_data(value) for key, value in record.args.items()}
            else:
                record.args = tuple(mask_sensitive_data(value) for value in record.args)
        return True


def install_sensitive_log_filter() -> None:
    root = logging.getLogger()
    if any(isinstance(item, SensitiveDataFilter) for item in root.filters):
        return
    root.addFilter(SensitiveDataFilter())
