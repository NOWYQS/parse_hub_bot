from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from services.webdav import WebDavArchiveConfig, _ensure_directory, archive_output, platform_folder


class _WebDavHandler(BaseHTTPRequestHandler):
    directories: set[str] = {"/dav/"}
    files: dict[str, bytes] = {}

    def log_message(self, format: str, *args: object) -> None:
        return

    def _authorized(self) -> bool:
        return self.headers.get("Authorization", "").startswith("Basic ")

    def do_MKCOL(self) -> None:
        if not self._authorized():
            self.send_response(401)
            self.end_headers()
            return
        path = unquote(urlsplit(self.path).path).rstrip("/") + "/"
        if path in self.directories:
            self.send_response(403)
        else:
            parent = str(Path(path.rstrip("/")).parent).rstrip("/") + "/"
            if parent not in self.directories:
                self.send_response(409)
            else:
                self.directories.add(path)
                self.send_response(201)
        self.end_headers()

    def do_PUT(self) -> None:
        if not self._authorized():
            self.send_response(401)
            self.end_headers()
            return
        path = unquote(urlsplit(self.path).path)
        parent = str(Path(path).parent).rstrip("/") + "/"
        if parent not in self.directories:
            self.send_response(409)
            self.end_headers()
            return
        length = int(self.headers["Content-Length"])
        self.files[path] = self.rfile.read(length)
        self.send_response(201)
        self.end_headers()

    def do_PROPFIND(self) -> None:
        if not self._authorized():
            self.send_response(401)
            self.end_headers()
            return
        path = unquote(urlsplit(self.path).path)
        directory = path.rstrip("/") + "/"
        if path not in self.files and directory not in self.directories:
            self.send_response(404)
            self.end_headers()
            return
        size = len(self.files[path]) if path in self.files else 0
        body = (
            '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"><d:response><d:propstat>'
            f"<d:prop><d:getcontentlength>{size}</d:getcontentlength></d:prop>"
            "</d:propstat></d:response></d:multistatus>"
        ).encode()
        self.send_response(207)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def webdav_server():
    _WebDavHandler.directories = {"/dav/"}
    _WebDavHandler.files = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _WebDavHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/dav"
    finally:
        server.shutdown()
        thread.join()


def test_platform_folder_uses_requested_root_labels() -> None:
    assert platform_folder("twitter") == "X"
    assert platform_folder("telegram") == "Telegram"
    assert platform_folder("youtube") == "YouTube"
    assert platform_folder("xhs") == "小红书"


def test_existing_directory_uses_trailing_slash_propfind(webdav_server: str) -> None:
    config = WebDavArchiveConfig(webdav_server, "archive-user", "secret")
    _WebDavHandler.directories.add("/dav/X/")
    _ensure_directory(config, "X")


def test_archive_output_groups_original_files_by_platform_and_verifies_size(tmp_path: Path, webdav_server: str) -> None:
    original = tmp_path / "原视频.mp4"
    original.write_bytes(b"original-media")
    nested = tmp_path / "assets" / "cover.jpg"
    nested.parent.mkdir()
    nested.write_bytes(b"cover")
    processed = tmp_path / "processed" / "converted.mp4"
    processed.parent.mkdir()
    processed.write_bytes(b"converted")

    config = WebDavArchiveConfig(webdav_server, "archive-user", "secret")
    archived = asyncio.run(
        archive_output(
            tmp_path,
            platform_id="twitter",
            raw_url="https://x.com/example/status/123",
            config=config,
            now=datetime(2026, 8, 21, 3, 4, 5, tzinfo=UTC),
        )
    )

    assert archived == ["X/202608/21110405_cover.jpg", "X/202608/21110405_原视频.mp4"]
    assert _WebDavHandler.files["/dav/X/202608/21110405_原视频.mp4"] == b"original-media"
    assert _WebDavHandler.files["/dav/X/202608/21110405_cover.jpg"] == b"cover"
    assert not any("processed" in path for path in _WebDavHandler.files)


def test_archive_skips_symlinks_escaping_output_dir(tmp_path: Path, webdav_server: str) -> None:
    original = tmp_path / "video.mp4"
    original.write_bytes(b"original-media")
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_bytes(b"secret-bytes")
    (tmp_path / "leak.txt").symlink_to(outside)

    config = WebDavArchiveConfig(webdav_server, "archive-user", "secret")
    archived = asyncio.run(
        archive_output(
            tmp_path,
            platform_id="telegram",
            raw_url="https://t.me/example/123",
            config=config,
            now=datetime(2026, 8, 21, 3, 4, 5, tzinfo=UTC),
        )
    )

    assert archived == ["Telegram/202608/21110405_video.mp4"]
    assert _WebDavHandler.files["/dav/Telegram/202608/21110405_video.mp4"] == b"original-media"
    assert not any("leak" in path for path in _WebDavHandler.files)
