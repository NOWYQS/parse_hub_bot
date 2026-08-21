from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_SCRIPT = REPO_ROOT / "docker" / "patch_parsehub_youtube.py"


def test_patch_sets_4g_group_limit_and_quality_first_av1_sort(tmp_path: Path) -> None:
    target = tmp_path / "youtube.py"
    target.write_text(
        '''class YtbVideoParseResult:\n'
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
    assert '"-f",\n            "(bv*+ba/b)[filesize<4G] / (bv*+ba/b)[filesize_approx<4G]",' in patched
    assert '"-S",\n            "res,fps,hdr,vcodec:av01",' in patched
    assert "+codec:h264,filesize~500M" not in patched
