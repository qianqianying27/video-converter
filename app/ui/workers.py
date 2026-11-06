"""后台任务：探测视频信息 + 生成缩略图。

放在 QThreadPool 里执行，避免批量添加视频时界面卡顿。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from ..media_info import MediaProbeError, probe_media
from ..thumbnail import ThumbnailError, extract_thumbnail


class WorkerSignals(QObject):
    done = Signal(object)


class MediaLoadWorker(QRunnable):
    """一次完成 ffprobe 探测与缩略图抽取，结果通过信号回传主线程。"""

    def __init__(self, path: Path, ffmpeg: Path, ffprobe: Path) -> None:
        super().__init__()
        self._path = path
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self.signals = WorkerSignals()

    def run(self) -> None:  # noqa: D401 - QRunnable 接口
        result = {
            "path": self._path,
            "info": None,
            "thumb": None,
            "error": "",
            "thumb_error": "",
        }
        try:
            info = probe_media(self._path, self._ffprobe)
        except MediaProbeError as exc:
            result["error"] = str(exc)
            self.signals.done.emit(result)
            return
        result["info"] = info
        try:
            result["thumb"] = extract_thumbnail(self._ffmpeg, self._path, info.duration)
        except ThumbnailError as exc:
            result["thumb_error"] = str(exc)
        self.signals.done.emit(result)
