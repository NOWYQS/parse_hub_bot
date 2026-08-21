#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

OLD = '''        if dl.get("live_status") in (
            "is_live",
            "is_upcoming",
            "was_live",
        ):
'''
NEW = '''        if dl.get("live_status") in (
            "is_live",
            "is_upcoming",
        ):
'''


def patch_file(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if OLD not in source:
        raise RuntimeError(f"expected ParseHub live-status block not found: {path}")
    path.write_text(source.replace(OLD, NEW, 1), encoding="utf-8")


def installed_ytdlp_module() -> Path:
    spec = importlib.util.find_spec("parsehub.parsers.base.ytdlp")
    if spec is None or spec.origin is None:
        raise RuntimeError("installed ParseHub yt-dlp module not found")
    return Path(spec.origin)


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) == 2 else installed_ytdlp_module()
    patch_file(target)


if __name__ == "__main__":
    main()
