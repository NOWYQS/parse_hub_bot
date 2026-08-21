from pathlib import Path
import ast
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_SCRIPT = REPO_ROOT / "docker" / "patch_parsehub_youtube.py"


def test_patch_sets_unlimited_quality_first_av1_sort(tmp_path: Path) -> None:
    target = tmp_path / "youtube.py"
    target.write_text(
        '''class YtbParse:\n'
        '    __match__ = r"^(http(s)?://).*youtu(be|.be)?(\\.com)?/(?!(live|post))(?!@).+"\n'
        '\n'
        'class YtbVideoParseResult:\n'
        '    @property\n'
        '    def cli_args(self) -> list[str]:\n'
        '        return [\n'
        '            *super().cli_args,\n'
        '            "-S",\n'
        '            "+codec:h264,filesize~500M",\n'
        '        ]\n'''.replace("'\n        '", ""),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(PATCH_SCRIPT), str(target)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    patched = target.read_text(encoding="utf-8")
    assert '"-f",\n            "bv*+ba/b",' in patched
    assert '"-S",\n            "res,fps,hdr,vcodec:av01",' in patched
    assert "filesize" not in patched
    assert "+codec:h264,filesize~500M" not in patched


def test_patch_allows_youtube_live_but_still_excludes_posts(tmp_path: Path) -> None:
    target = tmp_path / "youtube.py"
    target.write_text(
        '''class YtbParse:\n'
        '    __match__ = r"^(http(s)?://).*youtu(be|.be)?(\\.com)?/(?!(live|post))(?!@).+"\n'
        '\n'
        'class YtbVideoParseResult:\n'
        '    @property\n'
        '    def cli_args(self) -> list[str]:\n'
        '        return [\n'
        '            *super().cli_args,\n'
        '            "-S",\n'
        '            "+codec:h264,filesize~500M",\n'
        '        ]\n'''.replace("'\n        '", ""),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(PATCH_SCRIPT), str(target)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    tree = ast.parse(target.read_text(encoding="utf-8"))
    pattern = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__match__" for t in node.targets)
    )
    assert re.match(pattern, "https://www.youtube.com/live/abcdefghijk?si=example")
    assert not re.match(pattern, "https://www.youtube.com/post/Ugkx-example")
