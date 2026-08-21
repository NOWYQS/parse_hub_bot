from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from parsehub.types import DownloadResult, VideoFile


class FakeYouTubeResult:
    name = "video"
    cli_args = ["--quiet", "--no-progress", "-f", "bv*+ba/b", "-S", "res,fps,hdr,vcodec:av01"]
    dl = SimpleNamespace(width=3840, height=2160, duration=120)

    def __init__(self, candidate_sizes: list[int]):
        self.candidate_sizes = list(candidate_sizes)
        self.calls: list[list[str]] = []
        self.output_paths: list[Path] = []

    async def _run_download(self, cli_args: list[str], *, outtmpl: str, **kwargs: object) -> None:
        self.calls.append(cli_args)
        path = Path(outtmpl.replace("%(ext)s", "webm"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * self.candidate_sizes.pop(0))
        self.output_paths.append(path)


def _download_result(path: Path) -> DownloadResult:
    return DownloadResult(VideoFile(path=str(path), width=3840, height=2160, duration=120), path.parent)


def test_original_under_telegram_limit_is_reused(tmp_path: Path) -> None:
    assert importlib.util.find_spec("services.youtube_variants") is not None
    from services.youtube_variants import prepare_telegram_video

    original = tmp_path / "original.webm"
    original.write_bytes(b"x" * 500)
    parsed = FakeYouTubeResult([])
    result = _download_result(original)

    selected = asyncio.run(prepare_telegram_video(parsed, result, size_limit=1000))

    assert selected is result
    assert parsed.calls == []
    assert original.exists()


def test_oversized_original_downloads_smaller_variant_and_retries_actual_oversize(tmp_path: Path) -> None:
    assert importlib.util.find_spec("services.youtube_variants") is not None
    from services.youtube_variants import prepare_telegram_video

    original = tmp_path / "original.webm"
    original.write_bytes(b"x" * 1200)
    parsed = FakeYouTubeResult([1100, 700])
    result = _download_result(original)

    selected = asyncio.run(prepare_telegram_video(parsed, result, size_limit=1000))
    selected_media = selected.media
    selected_path = Path(selected_media.path)

    assert selected is not result
    assert selected.output_dir == result.output_dir
    assert selected_path.stat().st_size == 700
    assert original.stat().st_size == 1200
    assert len(parsed.calls) == 2
    assert any("filesize<950" in arg for arg in parsed.calls[0])
    assert any("filesize<800" in arg for arg in parsed.calls[1])
    assert not parsed.output_paths[0].exists()
