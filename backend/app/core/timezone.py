"""统一时区工具：项目所有时间戳用北京时间（Asia/Shanghai, UTC+8）。"""

from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))


def now_bjt() -> datetime:
    """返回当前北京时间（带时区信息）。"""
    return datetime.now(BJT)


def utcnow() -> datetime:
    """兼容旧代码：返回 naive 北京时间（无时区后缀，与数据库 timestamp 兼容）。"""
    return datetime.now(BJT).replace(tzinfo=None)
