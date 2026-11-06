"""应用入口。"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .env import BIN_DIR, ToolNotFoundError, resolve_tools
from .settings import AppSettings
from .ui.main_window import MainWindow

QSS = """
QMainWindow, QWidget#central { background: #f3f4f6; }

QLabel#titleLabel { font-size: 17pt; font-weight: 700; color: #1f2733; }
QLabel#subtitleLabel { color: #8a94a3; }
QLabel#hintLabel {
    color: #8a94a3; font-size: 11pt; background: #ffffff;
    border: 1px dashed #d5dae1; border-radius: 8px; padding: 24px;
}
QLabel#metaKey { color: #8a94a3; }
QLabel#metaValue { color: #232a35; }

QWidget#previewCard { background: #14171c; border-radius: 8px; }
QLabel#preview { background: transparent; }

QGroupBox {
    background: #ffffff;
    border: 1px solid #e2e5ea;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
    color: #39424f;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #39424f;
}

QPushButton {
    background: #ffffff;
    border: 1px solid #d6dbe2;
    border-radius: 6px;
    padding: 6px 14px;
    color: #2a3240;
}
QPushButton:hover { background: #f3f6fb; border-color: #b9c4d4; }
QPushButton:pressed { background: #e9eef7; }
QPushButton#primary {
    background: #2f6fed;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
}
QPushButton#primary:hover { background: #2861d8; }
QPushButton#primary:disabled { background: #b7c9ee; }

QLineEdit, QComboBox, QSpinBox {
    background: #ffffff;
    border: 1px solid #d6dbe2;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 22px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #2f6fed; }

QListWidget#videoList {
    background: #ffffff;
    border: 1px solid #e2e5ea;
    border-radius: 8px;
    padding: 4px;
}
QListWidget#videoList::item { padding: 6px; border-radius: 6px; }
QListWidget#videoList::item:selected { background: #e8f0fe; color: #1c2430; }
QListWidget#videoList::item:hover { background: #f4f7fc; }

QTableWidget#queueTable {
    background: #ffffff;
    border: none;
    alternate-background-color: #fafbfc;
}
QTableWidget#queueTable::item { padding: 4px 6px; }
QHeaderView::section {
    background: #f7f8fa;
    border: none;
    border-bottom: 1px solid #e6e9ee;
    padding: 6px;
    color: #6b7482;
    font-weight: 600;
}

QProgressBar {
    background: #e9edf3;
    border: none;
    border-radius: 9px;
    text-align: center;
    color: #33405a;
    font-size: 9pt;
}
QProgressBar::chunk { background: #2f6fed; border-radius: 9px; }
QProgressBar[state="done"]::chunk { background: #1f9d55; }
QProgressBar[state="failed"]::chunk { background: #d64545; }

QStatusBar { background: #eef0f4; color: #5c6675; }
"""


def _resolve_with_dialog(settings: AppSettings):
    """解析 ffmpeg；缺失时弹窗让用户定位，取消则返回 None。"""
    while True:
        try:
            return resolve_tools(settings.ffmpeg_path or None)
        except ToolNotFoundError as exc:
            box = QMessageBox()
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("缺少 ffmpeg")
            box.setText(str(exc))
            box.setInformativeText(
                "可以点「定位 ffmpeg…」选择 ffmpeg.exe；"
                "也可以运行 scripts/fetch_ffmpeg.ps1 自动下载到 bin\\ 目录。"
            )
            locate = box.addButton("定位 ffmpeg…", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("退出", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is locate:
                path, _ = QFileDialog.getOpenFileName(
                    None, "选择 ffmpeg 可执行文件", str(BIN_DIR),
                    "ffmpeg (ffmpeg.exe);;所有文件 (*.*)",
                )
                if path:
                    settings.ffmpeg_path = path
                    settings.sync()
                    continue
            return None


def main() -> int:
    selftest = "--selftest" in sys.argv
    if selftest:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(sys.argv)
    app.setApplicationName("VideoConverter")
    app.setOrganizationName("qianqianying27")
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(QSS)

    settings = AppSettings()

    if selftest:
        # 打包后的自检：确认 ffmpeg 能被定位、主窗口能正常构造，然后退出
        try:
            ffmpeg, ffprobe = resolve_tools(settings.ffmpeg_path or None)
        except ToolNotFoundError as exc:
            print(f"selftest failed: {exc}", file=sys.stderr)
            return 3
        window = MainWindow(ffmpeg, ffprobe, settings)
        window.show()
        QTimer.singleShot(600, app.quit)
        code = app.exec()
        print(f"selftest ok: ffmpeg={ffmpeg}", flush=True)
        return code

    tools = _resolve_with_dialog(settings)
    if tools is None:
        return 1
    ffmpeg, ffprobe = tools

    window = MainWindow(ffmpeg, ffprobe, settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
