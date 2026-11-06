"""应用入口。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .env import BIN_DIR, ToolNotFoundError, resolve_tools
from .settings import AppSettings
from .ui.main_window import MainWindow

QSS = """
QPushButton {
    padding: 5px 12px;
}
QPushButton#primary {
    background-color: #2f6fed;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
}
QPushButton#primary:hover { background-color: #3d7bf2; }
QPushButton#primary:disabled { background-color: #a9c0ef; }
QLabel#preview {
    background: #1c1f24;
    border-radius: 6px;
    padding: 6px;
    color: #b8c0cc;
}
QGroupBox {
    font-weight: 600;
    border: 1px solid #dcdfe5;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QListWidget#videoList {
    background: #ffffff;
    border: 1px solid #dcdfe5;
    border-radius: 6px;
}
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
    app = QApplication(sys.argv)
    app.setApplicationName("VideoConverter")
    app.setOrganizationName("qianqianying27")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    settings = AppSettings()
    tools = _resolve_with_dialog(settings)
    if tools is None:
        return 1
    ffmpeg, ffprobe = tools

    window = MainWindow(ffmpeg, ffprobe, settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
