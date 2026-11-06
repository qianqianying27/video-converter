"""转换队列：多文件顺序转换、状态机、取消。

同一时刻只跑一个 ffmpeg 进程（避免 CPU 抢占导致每个都变慢），
队列负责前后衔接并把状态变化通知给界面。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .converter import ConversionJob
from .presets import Preset, build_args, output_path

PENDING = "等待中"
RUNNING = "转换中"
SUCCESS = "完成"
FAILED = "失败"
CANCELLED = "已取消"


@dataclass
class QueueJob:
    index: int
    source: Path
    output: Path
    preset: Preset
    duration: float
    args: list[str]
    state: str = PENDING
    progress: float = 0.0
    detail: str = ""
    error: str = ""

    @property
    def is_finished(self) -> bool:
        return self.state in (SUCCESS, FAILED, CANCELLED)


class ConversionQueue(QObject):
    job_added = Signal(int)
    job_changed = Signal(int)
    busy_changed = Signal(bool)
    all_finished = Signal()

    def __init__(self, ffmpeg: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ffmpeg = ffmpeg
        self._jobs: list[QueueJob] = []
        self._runner: ConversionJob | None = None
        self._current: QueueJob | None = None

    # ---------- 属性 ----------

    @property
    def jobs(self) -> list[QueueJob]:
        return list(self._jobs)

    @property
    def busy(self) -> bool:
        return self._runner is not None

    def set_ffmpeg(self, ffmpeg: Path) -> None:
        """切换 ffmpeg（设置中手动指定后调用）。"""
        self._ffmpeg = ffmpeg

    # ---------- 入队 / 启动 ----------

    def add(
        self,
        source: Path,
        preset: Preset,
        out_dir: Path,
        duration: float,
        *,
        crf: int = 23,
        height: int | None = None,
    ) -> QueueJob:
        out_dir.mkdir(parents=True, exist_ok=True)
        output = output_path(source, preset, out_dir)
        args = build_args(self._ffmpeg, preset, source, output, crf=crf, height=height)
        job = QueueJob(
            index=len(self._jobs),
            source=source,
            output=output,
            preset=preset,
            duration=duration,
            args=args,
        )
        self._jobs.append(job)
        self.job_added.emit(job.index)
        return job

    def start(self) -> None:
        """开始执行队列中第一个等待任务（空闲时调用）。"""
        if self._runner is not None:
            return
        for job in self._jobs:
            if job.state == PENDING:
                self._launch(job)
                return
        self.all_finished.emit()

    def _launch(self, job: QueueJob) -> None:
        job.state = RUNNING
        job.progress = 0.0
        job.detail = ""
        job.error = ""
        self._current = job
        self.job_changed.emit(job.index)
        self.busy_changed.emit(True)

        runner = ConversionJob(job.args, job.output, job.duration, self)
        runner.progress.connect(self._on_progress)
        runner.finished.connect(self._on_finished)
        self._runner = runner
        runner.start()

    # ---------- 进度 / 结束 ----------

    def _on_progress(self, info) -> None:  # ProgressInfo
        job = self._current
        if job is None:
            return
        if info.percent is not None:
            job.progress = info.percent
        parts: list[str] = []
        if info.speed:
            parts.append(f"{info.speed:.2f}x")
            if info.seconds and info.speed > 0 and job.duration:
                remain = max(0.0, (job.duration - info.seconds) / info.speed)
                parts.append(f"剩余约 {remain:.0f}s")
        job.detail = " · ".join(parts)
        self.job_changed.emit(job.index)

    def _on_finished(self, ok: bool, message: str) -> None:
        job = self._current
        self._runner = None
        self._current = None
        if job is not None:
            if ok:
                job.state = SUCCESS
                job.progress = 100.0
            elif message == "已取消":
                job.state = CANCELLED
            else:
                job.state = FAILED
                job.error = message
            self.job_changed.emit(job.index)
        self.busy_changed.emit(False)
        self._start_next()

    def _start_next(self) -> None:
        for job in self._jobs:
            if job.state == PENDING:
                self._launch(job)
                return
        self.all_finished.emit()

    # ---------- 取消 ----------

    def cancel(self, index: int) -> None:
        if not (0 <= index < len(self._jobs)):
            return
        job = self._jobs[index]
        if job is self._current and self._runner is not None:
            self._runner.cancel()
        elif job.state == PENDING:
            job.state = CANCELLED
            self.job_changed.emit(job.index)
            self._start_next()

    def cancel_current(self) -> None:
        if self._current is not None:
            self.cancel(self._current.index)

    def clear_finished(self) -> None:
        self._jobs = [j for j in self._jobs if not j.is_finished]
        for i, job in enumerate(self._jobs):
            job.index = i
        for job in self._jobs:
            self.job_changed.emit(job.index)
