"""跑起主界面、真实执行一次转换并截图（README / 交付文档用）。

用法：
    python scripts/screenshot.py [--scale-limit N]

前置：仓库根目录 .samples/ 下有 flower.mp4（横屏）与 portrait.mp4（竖屏）。
    可用 scripts/fetch_samples.ps1 获取/生成。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import os

if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.env import resolve_tools  # noqa: E402
from app.main import QSS  # noqa: E402
from app.settings import AppSettings  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def _install_cjk_font(app: QApplication) -> None:
    """离屏渲染时系统字体可能不可见，显式加载中文字体。"""
    for candidate in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        font_id = QFontDatabase.addApplicationFont(candidate)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))
                return


def _wait(app: QApplication, predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _select(window: MainWindow, path: Path) -> bool:
    item = window._items.get(path.resolve())
    if item is None:
        return False
    window.video_list.setCurrentItem(item)
    app = QApplication.instance()
    app.processEvents()
    return True


def main() -> int:
    landscape = (ROOT / ".samples" / "flower.mp4")
    portrait = (ROOT / ".samples" / "portrait.mp4")
    for p in (landscape, portrait):
        if not p.exists():
            print(f"缺少素材：{p}（先运行 scripts/fetch_samples.ps1）", file=sys.stderr)
            return 2

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(QSS)
    _install_cjk_font(app)

    ffmpeg, ffprobe = resolve_tools(None)
    window = MainWindow(ffmpeg, ffprobe, AppSettings())
    window.resize(1200, 900)
    window.show()

    out_dir = ROOT / ".samples" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("flower_mp4*"):
        old.unlink(missing_ok=True)

    window._add_files([str(landscape), str(portrait)])
    _wait(app, lambda: len(window._infos) == 2, 30)
    window.output_edit.setText(str(out_dir))

    # 截图 1：横屏视频 + 一次真实的 MP4 转换（队列状态与设置一致）
    _select(window, landscape)
    index = window.preset_combo.findData("mp4")
    if index >= 0:
        window.preset_combo.setCurrentIndex(index)
    app.processEvents()
    started = time.time()
    window.convert_btn.click()
    _wait(app, lambda: bool(window._queue.jobs) and window._queue.jobs[0].is_finished, 120)
    elapsed = time.time() - started
    if window._queue.jobs:
        job = window._queue.jobs[0]
        window.statusBar().showMessage(f"转换完成：{job.output.name}（耗时 {elapsed:.1f}s）", 0)
    app.processEvents()
    window.grab().save(str(ROOT / "docs" / "screenshot.png"))

    # 截图 2：竖屏视频（验证旋转/竖屏分辨率展示）
    _select(window, portrait)
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    window.grab().save(str(ROOT / "docs" / "screenshot-portrait.png"))

    print("已保存 docs/screenshot.png 与 docs/screenshot-portrait.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
