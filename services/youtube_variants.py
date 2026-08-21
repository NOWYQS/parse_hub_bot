from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from parsehub.types import DownloadResult, ProgressCallback, VideoFile

from log import logger
from utils.helpers import to_list
from utils.media_processing_unit import MediaProcessingUnit

logger = logger.bind(name="YouTubeVariant")

_CAP_RATIOS = (0.95, 0.80, 0.65, 0.50, 0.35, 0.25)


def needs_telegram_variant(
    download_result: DownloadResult,
    *,
    size_limit: int = MediaProcessingUnit.TG_MAX_VIDEO_SIZE,
) -> bool:
    media = to_list(download_result.media)
    if len(media) != 1 or not isinstance(media[0], VideoFile):
        return False
    return Path(media[0].path).stat().st_size > size_limit


def _format_args(cli_args: list[str], size_cap: int) -> list[str]:
    selector = f"(bv*+ba/b)[filesize<{size_cap}] / (bv*+ba/b)[filesize_approx<{size_cap}]"
    args = cli_args.copy()
    try:
        index = args.index("-f")
    except ValueError:
        args.extend(["-f", selector])
    else:
        args[index + 1] = selector
    return args


async def prepare_telegram_video(
    parse_result: Any,
    download_result: DownloadResult,
    *,
    size_limit: int = MediaProcessingUnit.TG_MAX_VIDEO_SIZE,
    proxy: str | None = None,
    callback: ProgressCallback | None = None,
    callback_args: tuple = (),
    callback_kwargs: dict | None = None,
) -> DownloadResult:
    if not needs_telegram_variant(download_result, size_limit=size_limit):
        return download_result

    output_root = Path(download_result.output_dir)
    telegram_root = output_root / "telegram"
    caps = tuple(dict.fromkeys(max(1, int(size_limit * ratio)) for ratio in _CAP_RATIOS))

    for attempt, cap in enumerate(caps, start=1):
        attempt_dir = telegram_root / f"attempt-{attempt:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = f"{attempt_dir.joinpath(parse_result.name)}.%(ext)s"
        cli_args = _format_args(parse_result.cli_args, cap)
        logger.info(f"下载 TG 降级版本: attempt={attempt}/{len(caps)}, cap={cap}")

        try:
            await parse_result._run_download(
                cli_args,
                outtmpl=outtmpl,
                connections=4,
                proxy=proxy,
                callback=callback,
                callback_args=callback_args,
                callback_kwargs=callback_kwargs or {},
            )
            files = sorted(p for p in attempt_dir.glob(f"{parse_result.name}.*") if p.is_file())
            if not files:
                raise RuntimeError("TG 降级下载完成但未找到文件")
            selected = files[0]
            actual_size = selected.stat().st_size
            if actual_size > size_limit:
                logger.warning(f"TG 降级版本仍超限: attempt={attempt}, actual={actual_size}, limit={size_limit}")
                shutil.rmtree(attempt_dir, ignore_errors=True)
                continue

            return DownloadResult(
                VideoFile(
                    path=str(selected),
                    width=parse_result.dl.width,
                    height=parse_result.dl.height,
                    duration=parse_result.dl.duration,
                ),
                download_result.output_dir,
            )
        except Exception:
            shutil.rmtree(attempt_dir, ignore_errors=True)
            raise

    raise RuntimeError(f"无法下载小于 Telegram 限制 ({size_limit} bytes) 的视频版本")
