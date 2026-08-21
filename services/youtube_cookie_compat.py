"""YouTube cookie 文件路径兼容补丁。

parsehub 2.1.11 的 `YtbParse.get_cookie_text()` 会把字典形式 cookie 转成 Netscape
格式，但转换过程会丢失 `Secure`/`HttpOnly` 标志，导致 `__Secure-*` 这类 YouTube
登录 cookie 被 yt-dlp 忽略，仍然报 "Sign in to confirm you're not a bot"。

本模块把 `YtbParse.get_cookie_text` 替换为支持文件路径的版本：

- 若平台配置中 cookie 值为一个存在的文件路径（例如 `/run/secrets/youtube-cookies.txt`），
  直接读取该文件的 Netscape 格式内容（保留全部标志）；
- 否则保持原有的字典 → Netscape 转换行为不变。

启用方式：在 bot 启动路径中 `import services.youtube_cookie_compat`。
"""
from __future__ import annotations

from pathlib import Path

from parsehub.parsers.parser.youtube import YtbParse


def _cookie_text_with_file_support(self: YtbParse) -> str | None:
    cookie = self.cookie.get_value()
    if not cookie:
        return None
    # 兼容: 配置值为 Netscape cookie 文件路径（单键且该键是存在的文件，值为空）
    if len(cookie) == 1:
        (key, value), = cookie.items()
        if not value and key.startswith("/") and Path(key).is_file():
            return Path(key).read_text(encoding="utf-8")
    return self.to_netscape_cookie(cookie, "youtube.com")


def apply() -> None:
    """替换 YtbParse.get_cookie_text，幂等。"""
    if getattr(YtbParse, "get_cookie_text") is not _cookie_text_with_file_support:
        YtbParse.get_cookie_text = _cookie_text_with_file_support  # type: ignore[method-assign]


apply()
