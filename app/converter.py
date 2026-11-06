"""单个转换任务：基于 QProcess 的异步 ffmpeg 调用。

- 进度：解析 ffmpeg ``-progress pipe:1`` 的 stdout
- 失败：保留 stderr 末尾信息，转成可读中文提示
- 取消：kill 进程并删除半成品文件
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from .progress import ProgressInfo, ProgressParser

CREATE_NO_WINDOW_FLAG = 0x08000000
STDERR_TAIL_LIMIT = 8000


class ConversionJob(QObject):
    """一个 ffmpeg 进程的生命周期封装。"""

    progress = Signal(object)          # ProgressInfo
    finished = Signal(bool, str)       # (成功?, 失败/取消原因)

    def __init__(
        self,
        args: list[str],
        output: Path,
        duration: float,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._output = output
        self._parser = ProgressParser(duration)
        self._buffer = ""
        self._stderr = ""
        self._cancelled = False
        self._process = QProcess(self)
        self._process.setProgram(args[0])
        self._process.setArguments(args[1:])
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._attach_no_window()

    # ---------- 启动 / 取消 ----------

    def start(self) -> None:
        self._process.start()

    def cancel(self) -> None:
        self._cancelled = True
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(3000)

    @property
    def running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    # ---------- 进程输出 ----------

    def _on_stdout(self) -> None:
        raw = bytes(self._process.readAllStandardOutput()).decode("utf-8", "replace")
        self._buffer += raw
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            info = self._parser.feed(line)
            if info is not None:
                self.progress.emit(info)

    def _on_stderr(self) -> None:
        raw = bytes(self._process.readAllStandardError()).decode("utf-8", "replace")
        self._stderr = (self._stderr + raw)[-STDERR_TAIL_LIMIT:]

    # ---------- 结束处理 ----------

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.finished.emit(False, "ffmpeg 启动失败，请检查可执行文件路径是否正确。")

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        # 把剩余输出读完，避免最后一块进度丢失
        self._on_stdout()
        self._on_stderr()

        if self._cancelled:
            self._remove_partial()
            self.finished.emit(False, "已取消")
            return

        if exit_code == 0 and self._output.exists() and self._output.stat().st_size > 0:
            self.finished.emit(True, "")
            return

        self._remove_partial()
        self.finished.emit(False, self._error_message(exit_code))

    def _error_message(self, exit_code: int) -> str:
        lines = [ln.strip() for ln in self._stderr.strip().splitlines() if ln.strip()]
        detail = lines[-1] if lines else f"ffmpeg 退出码 {exit_code}"
        return f"转换失败：{detail}"

    def _remove_partial(self) -> None:
        try:
            if self._output.exists():
                self._output.unlink()
        except OSError:
            pass

    def _attach_no_window(self) -> None:
        """Windows 下隐藏 ffmpeg 控制台窗口。"""
        if sys.platform != "win32":
            return
        try:
            def _modifier(args):  # QProcess.CreateProcessArguments
                args.flags |= CREATE_NO_WINDOW_FLAG

            self._process.setCreateProcessArgumentsModifier(_modifier)
        except (AttributeError, TypeError):
            pass
