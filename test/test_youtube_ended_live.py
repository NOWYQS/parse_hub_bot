from __future__ import annotations

import asyncio

import pytest
from parsehub.errors import ParseError
from parsehub.parsers.base.ytdlp import YtParser


class StubYtParser(YtParser, register=False):
    def __init__(self, live_status: str) -> None:
        self.live_status = live_status

    async def _extract_info(self, url: str) -> dict:
        return {
            "live_status": self.live_status,
            "title": "fixture",
            "description": "fixture",
            "thumbnail": "https://example.invalid/thumb.jpg",
            "duration": 60,
            "width": 1920,
            "height": 1080,
        }


def test_ended_youtube_live_is_parseable() -> None:
    result = asyncio.run(StubYtParser("was_live")._parse("https://www.youtube.com/live/fixture"))

    assert result.title == "fixture"
    assert result.info_json["live_status"] == "was_live"


def test_current_youtube_live_is_still_rejected() -> None:
    with pytest.raises(ParseError, match="不支持直播"):
        asyncio.run(StubYtParser("is_live")._parse("https://www.youtube.com/live/fixture"))
