"""队列集成测试：真实跑一次 QProcess 转换，验证进度与状态机。"""

from __future__ import annotations

import time

from app.presets import get_preset
from app.queue import SUCCESS, ConversionQueue


def test_queue_converts_file(qapp, tools, sample_video, tmp_path):
    ffmpeg, _ = tools
    queue = ConversionQueue(ffmpeg)
    progress_values: list[float] = []
    queue.job_changed.connect(lambda i: progress_values.append(queue.jobs[i].progress))

    job = queue.add(sample_video, get_preset("mp3"), tmp_path, duration=2.0)
    queue.start()

    deadline = time.time() + 90
    while time.time() < deadline:
        qapp.processEvents()
        if job.is_finished:
            break
        time.sleep(0.02)

    assert job.state == SUCCESS, job.error
    assert job.output.exists() and job.output.stat().st_size > 0
    assert job.output.name.startswith("sample_mp3")
    assert progress_values, "应当收到进度更新"


def test_queue_marks_failure(qapp, tools, tmp_path):
    """给一个不存在的输入文件，任务应进入失败状态而不是崩溃。"""
    ffmpeg, _ = tools
    queue = ConversionQueue(ffmpeg)
    missing = tmp_path / "missing.mkv"
    job = queue.add(missing, get_preset("mp4"), tmp_path, duration=10.0)
    queue.start()

    deadline = time.time() + 30
    while time.time() < deadline:
        qapp.processEvents()
        if job.is_finished:
            break
        time.sleep(0.02)

    assert job.state == "失败"
    assert job.error
