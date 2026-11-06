"""运行环境与外部工具定位。

优先级：用户手动指定 > 项目内置 bin/ > 系统 PATH。
所有子进程调用统一走 :func:`run_capture`，Windows 下不会弹出控制台窗口。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
BIN_DIR = APP_DIR / "bin"
THUMB_CACHE_DIR = Path(tempfile.gettempdir()) / "video_converter_thumbs"

# subprocess 的 CREATE_NO_WINDOW：避免调用 ffmpeg 时闪黑框
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0

EXE_SUFFIX = ".exe" if sys.platform == "win32" else ""


class ToolNotFoundError(RuntimeError):
    """找不到可用的 ffmpeg/ffprobe。"""


def run_capture(cmd: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
    """执行外部命令并捕获输出（不弹控制台窗口）。

    Raises:
        subprocess.TimeoutExpired: 超时
        OSError: 可执行文件不存在
    """
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def _works(exe: Path) -> bool:
    try:
        cp = run_capture([str(exe), "-version"], timeout=10)
        return cp.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _candidates(configured_ffmpeg: str | None) -> list[Path]:
    cands: list[Path] = []
    if configured_ffmpeg:
        p = Path(configured_ffmpeg).expanduser()
        if p.is_dir():
            p = p / f"ffmpeg{EXE_SUFFIX}"
        cands.append(p)
    cands.append(BIN_DIR / f"ffmpeg{EXE_SUFFIX}")
    which = shutil.which("ffmpeg")
    if which:
        cands.append(Path(which))
    return cands


def resolve_tools(configured_ffmpeg: str | None = None) -> tuple[Path, Path]:
    """返回 (ffmpeg, ffprobe) 可执行文件路径。

    Raises:
        ToolNotFoundError: 两者任一不可用
    """
    ffmpeg: Path | None = None
    for cand in _candidates(configured_ffmpeg):
        if cand.exists() and _works(cand):
            ffmpeg = cand
            break
    if ffmpeg is None:
        raise ToolNotFoundError(
            "未找到可用的 ffmpeg。请将 ffmpeg.exe / ffprobe.exe 放入 bin\\ 目录，"
            "或在「设置」中手动指定 ffmpeg.exe 路径。"
        )

    ffprobe = ffmpeg.with_name(f"ffprobe{EXE_SUFFIX}")
    if not (ffprobe.exists() and _works(ffprobe)):
        which = shutil.which("ffprobe")
        if which and _works(Path(which)):
            ffprobe = Path(which)
        else:
            raise ToolNotFoundError(
                "找到了 ffmpeg，但缺少配套的 ffprobe。请确保两者位于同一目录。"
            )
    return ffmpeg, ffprobe


def ensure_thumbnail_dir() -> Path:
    THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return THUMB_CACHE_DIR
