"""GUI 冒烟测试：无头模式下构造主窗口，确保界面能正常初始化。"""

from __future__ import annotations

import time

from app.ui.main_window import MainWindow


def test_main_window_constructs(qapp, tools):
    from app.settings import AppSettings

    ffmpeg, ffprobe = tools
    window = MainWindow(ffmpeg, ffprobe, AppSettings())
    assert window.windowTitle() == "视频格式转换器"
    assert window.video_list.count() == 0
    assert window.preset_combo.count() >= 5
    window.close()


def test_add_file_and_convert(qapp, tools, sample_video, tmp_path):
    """走一遍真实交互链路：添加文件 → 读取信息/缩略图 → 点开始转换 → 完成。"""
    from app.settings import AppSettings
    from app.queue import SUCCESS

    ffmpeg, ffprobe = tools
    window = MainWindow(ffmpeg, ffprobe, AppSettings())

    window._add_files([str(sample_video)])
    deadline = time.time() + 30
    while time.time() < deadline:
        qapp.processEvents()
        if sample_video.resolve() in window._infos:
            break
        time.sleep(0.02)
    assert sample_video.resolve() in window._infos
    assert sample_video.resolve() in window._thumbs  # 缩略图也生成成功

    window.output_edit.setText(str(tmp_path))
    index = window.preset_combo.findData("mp3")
    window.preset_combo.setCurrentIndex(index)
    window._start_conversion()

    deadline = time.time() + 60
    while time.time() < deadline:
        qapp.processEvents()
        if window._queue.jobs and window._queue.jobs[0].is_finished:
            break
        time.sleep(0.02)

    job = window._queue.jobs[0]
    assert job.state == SUCCESS, job.error
    assert job.output.exists()
    window.close()

