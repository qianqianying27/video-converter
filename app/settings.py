"""QSettings 封装：记住窗口几何、上次目录、格式与输出设置。"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings

ORG = "qianqianying27"
APP = "VideoConverter"

DEFAULTS: dict[str, object] = {
    "geometry": QByteArray(),
    "last_input_dir": "",
    "output_dir": "",
    "preset": "mp4",
    "resolution": "保持原分辨率",
    "crf": 23,
    "ffmpeg_path": "",
}


class AppSettings:
    def __init__(self) -> None:
        self._s = QSettings(ORG, APP)

    def get(self, key: str, default: object = None):
        if key in DEFAULTS:
            default = DEFAULTS[key]
        return self._s.value(key, default)

    def set(self, key: str, value: object) -> None:
        self._s.setValue(key, value)

    def sync(self) -> None:
        self._s.sync()

    # 便捷属性
    @property
    def ffmpeg_path(self) -> str:
        return str(self.get("ffmpeg_path") or "")

    @ffmpeg_path.setter
    def ffmpeg_path(self, value: str) -> None:
        self.set("ffmpeg_path", value)
