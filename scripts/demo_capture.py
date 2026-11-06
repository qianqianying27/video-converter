"""录制一段界面演示 GIF：加载视频 → 选择 WebM → 点击转换 → 进度 → 完成。

用法：python scripts/demo_capture.py
前置：.samples/bench_1080p.mp4（30s 1080p，由 scripts/fetch_samples.ps1 或手动生成）
产物：docs/demo.gif
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.env import resolve_tools  # noqa: E402
from app.main import QSS  # noqa: E402
from app.settings import AppSettings  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402

FPS = 5
FRAME_INTERVAL = 1.0 / FPS


def _install_cjk_font(app: QApplication) -> None:
    for candidate in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        font_id = QFontDatabase.addApplicationFont(candidate)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))
                return


class Recorder:
    def __init__(self, app: QApplication, window: MainWindow, frame_dir: Path) -> None:
        self.app = app
        self.window = window
        self.frame_dir = frame_dir
        self.count = 0

    def frame(self) -> None:
        self.app.processEvents()
        self.window.grab().save(str(self.frame_dir / f"frame_{self.count:04d}.png"))
        self.count += 1

    def hold(self, seconds: float) -> None:
        deadline = time.time() + seconds
        last = 0.0
        while time.time() < deadline:
            now = time.time()
            if now - last >= FRAME_INTERVAL:
                self.frame()
                last = now
            self.app.processEvents()
            time.sleep(0.01)


def main() -> int:
    src = ROOT / ".samples" / "bench_1080p.mp4"
    if not src.exists():
        print(f"缺少演示素材：{src}", file=sys.stderr)
        return 2

    frame_dir = ROOT / ".samples" / "demo_frames"
    if frame_dir.exists():
        for f in frame_dir.glob("frame_*.png"):
            f.unlink()
    frame_dir.mkdir(parents=True, exist_ok=True)

    out_dir = ROOT / ".samples" / "demo_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("bench_1080p_webm*"):
        old.unlink(missing_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(QSS)
    _install_cjk_font(app)

    ffmpeg, ffprobe = resolve_tools(None)
    window = MainWindow(ffmpeg, ffprobe, AppSettings())
    window.resize(1200, 900)
    window.show()

    window._add_files([str(src)])
    deadline = time.time() + 30
    while time.time() < deadline:
        app.processEvents()
        if src.resolve() in window._infos and src.resolve() in window._thumbs:
            break
        time.sleep(0.03)
    window.output_edit.setText(str(out_dir))

    index = window.preset_combo.findData("webm")
    if index >= 0:
        window.preset_combo.setCurrentIndex(index)
    window.resolution_combo.setCurrentText("720p")
    app.processEvents()

    rec = Recorder(app, window, frame_dir)
    rec.hold(3.0)  # 开场：文件已加载、缩略图与信息可见

    started = time.time()
    QTest.mouseClick(window.convert_btn, Qt.MouseButton.LeftButton)
    while time.time() - started < 180:
        app.processEvents()
        rec.frame()
        jobs = window._queue.jobs
        if jobs and jobs[0].is_finished:
            break
        time.sleep(FRAME_INTERVAL)
    elapsed = time.time() - started
    rec.hold(4.0)  # 结束：显示完成状态

    print(f"捕获 {rec.count} 帧，转换耗时 {elapsed:.1f}s")

    gif = ROOT / "docs" / "demo.gif"
    cmd = [
        str(ffmpeg), "-hide_banner", "-y",
        "-framerate", str(FPS),
        "-i", str(frame_dir / "frame_%04d.png"),
        "-vf",
        "scale=900:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=160[p];[s1][p]paletteuse",
        str(gif),
    ]
    cp = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if cp.returncode != 0:
        print(cp.stderr[-800:], file=sys.stderr)
        return cp.returncode
    print(f"已生成：{gif}（{gif.stat().st_size / 1024 / 1024:.1f} MB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
