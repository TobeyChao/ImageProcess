"""Translate raw exceptions into Chinese user-facing messages.

Each entry in ERROR_PATTERNS is (matcher, message_template, hint).
Matcher is either an exception class (isinstance check) or a callable
(exc) -> bool. First match wins. If nothing matches we return the raw
type+message and tell the user to check logs.
"""
from typing import Callable, Union

Matcher = Union[type, Callable[[Exception], bool]]
Pattern = tuple[Matcher, str, str]


def _has(*needles: str):
    """Build a matcher that returns True if any needle is in str(exc).lower()."""
    def _check(exc: Exception) -> bool:
        s = str(exc).lower()
        return any(n.lower() in s for n in needles)
    return _check


# Order matters — earlier patterns win.
ERROR_PATTERNS: list[Pattern] = [
    # Image dimension mismatch (must come before generic ValueError fallthrough)
    (_has("尺寸不一致", "size differ"),
     "黑底图和白底图尺寸不一致", "请确认两张图来自同一拍摄"),

    # API key family
    (_has("api key", "401", "unauthorized", "invalid_api_key"),
     "API Key 无效或已过期", "请到「设置」检查 Key 是否正确"),
    (_has("rate limit", "429", "throttling", "too many requests"),
     "API 调用太频繁，请稍后再试", "建议等待 30 秒后重试"),
    (_has("quota", "billing", "insufficient_quota"),
     "API 配额已用完", "请检查 API 控制台账单"),
    (_has("safety", "blocked"),
     "内容被安全过滤器拦截", "请修改提示词后重试"),

    # GPU / model
    (_has("cuda out of memory", "out of memory"),
     "显存不足", "尝试关闭其他占用 GPU 的程序，或在设置中改用 CPU"),
    (_has("model.safetensors", "缺少模型文件"),
     "模型文件缺失", "请先在设置页下载 BiRefNet 模型"),

    # Filesystem
    (FileNotFoundError, "找不到文件: {msg}", "请检查路径是否正确"),
    (PermissionError, "没有权限访问: {msg}", "请检查文件权限或以管理员身份运行"),

    # Network
    (_has("connection", "timeout", "network"),
     "网络请求失败", "请检查网络连接后重试"),
]


def user_message(exc: Exception) -> tuple[str, str]:
    """Return (msg, hint). Falls back to '<Type>: <raw>' / '查看日志了解详情'."""
    for matcher, msg_tpl, hint in ERROR_PATTERNS:
        matched = (
            isinstance(matcher, type) and isinstance(exc, matcher)
        ) or (
            callable(matcher) and not isinstance(matcher, type) and matcher(exc)
        )
        if matched:
            return msg_tpl.format(msg=str(exc)), hint

    return f"{type(exc).__name__}: {exc}", "查看日志了解详情"
