"""pytest 公共配置与共享 fixture。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# GUI 测试无头运行（必须在创建 QApplication 之前设置）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def tools():
    """返回 (ffmpeg, ffprobe)；找不到时跳过依赖 ffmpeg 的测试。"""
    from app.env import ToolNotFoundError, resolve_tools

    try:
        return resolve_tools(str(ROOT / "bin" / "ffmpeg.exe"))
    except ToolNotFoundError:
        pytest.skip("未找到 ffmpeg/ffprobe，跳过集成测试")


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory, tools):
    """用 lavfi 现场生成一个 2 秒、640x360、带音轨的测试视频。"""
    from app.env import run_capture

    ffmpeg, _ = tools
    out = tmp_path_factory.mktemp("media") / "sample.mp4"
    cmd = [
        str(ffmpeg), "-hide_banner", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "2",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        str(out),
    ]
    cp = run_capture(cmd, timeout=120)
    assert cp.returncode == 0, cp.stderr
    assert out.exists()
    return out


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app
