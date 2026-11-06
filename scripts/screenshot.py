"""用离屏模式跑起主界面并截图（用于 README / 交付文档）。

用法：python scripts/screenshot.py [视频路径]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.env import resolve_tools  # noqa: E402
from app.main import QSS  # noqa: E402
from app.presets import get_preset  # noqa: E402
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


def main() -> int:
    video = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "sample.mp4"
    if not video.exists():
        print(f"找不到演示视频：{video}", file=sys.stderr)
        return 2

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    _install_cjk_font(app)
    ffmpeg, ffprobe = resolve_tools(None)
    window = MainWindow(ffmpeg, ffprobe, AppSettings())
    window.resize(1180, 860)
    window.show()

    window._add_files([str(video)])
    deadline = time.time() + 30
    while time.time() < deadline:
        app.processEvents()
        if video.resolve() in window._infos and video.resolve() in window._thumbs:
            break
        time.sleep(0.05)
    app.processEvents()

    # 放一条排队中的任务，截图里能看到队列区域
    if video.resolve() in window._infos:
        info = window._infos[video.resolve()]
        window._queue.add(video.resolve(), get_preset("webm"),
                          Path(window.output_edit.text() or ROOT), info.duration)
    app.processEvents()

    out = ROOT / "docs" / "screenshot.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    window.statusBar().showMessage("就绪", 0)
    window.grab().save(str(out))
    print(f"已保存：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
