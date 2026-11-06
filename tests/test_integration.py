"""集成测试：真实调用 ffmpeg/ffprobe。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.media_info import probe_media
from app.presets import build_args, get_preset, output_path
from app.thumbnail import extract_thumbnail
from app.env import run_capture


def test_probe_sample(sample_video, tools):
    _, ffprobe = tools
    info = probe_media(sample_video, ffprobe)
    assert info.has_video and info.has_audio
    assert (info.width, info.height) == (640, 360)
    assert info.video_codec == "h264"
    assert 1.5 <= info.duration <= 2.6


def test_thumbnail_extracted(sample_video, tools):
    ffmpeg, _ = tools
    thumb = extract_thumbnail(ffmpeg, sample_video, 2.0, use_cache=False)
    assert thumb.exists() and thumb.stat().st_size > 0
    assert thumb.suffix == ".jpg"


def _convert(tools, preset_key: str, src: Path, out_dir: Path, **kwargs) -> Path:
    ffmpeg, _ = tools
    preset = get_preset(preset_key)
    dst = output_path(src, preset, out_dir)
    cp = run_capture(build_args(ffmpeg, preset, src, dst, **kwargs), timeout=240)
    assert cp.returncode == 0, cp.stderr
    assert dst.exists() and dst.stat().st_size > 0
    return dst


def test_convert_to_webm(sample_video, tools, tmp_path):
    dst = _convert(tools, "webm", sample_video, tmp_path, crf=40)
    _, ffprobe = tools
    info = probe_media(dst, ffprobe)
    assert info.video_codec == "vp9"
    assert info.has_audio


def test_convert_with_target_height(sample_video, tools, tmp_path):
    dst = _convert(tools, "mp4", sample_video, tmp_path, height=240)
    _, ffprobe = tools
    info = probe_media(dst, ffprobe)
    assert info.height == 240
    assert 420 <= info.width <= 430  # 640x360 等比缩到高 240，宽约 426


def test_extract_mp3(sample_video, tools, tmp_path):
    dst = _convert(tools, "mp3", sample_video, tmp_path)
    _, ffprobe = tools
    info = probe_media(dst, ffprobe)
    assert info.has_audio
    assert not info.has_video


def test_convert_to_gif(sample_video, tools, tmp_path):
    dst = _convert(tools, "gif", sample_video, tmp_path)
    assert dst.stat().st_size > 0


def test_mkv_copy_is_lossless(sample_video, tools, tmp_path):
    dst = _convert(tools, "mkv", sample_video, tmp_path)
    _, ffprobe = tools
    info = probe_media(dst, ffprobe)
    assert info.video_codec == "h264"  # copy 不重新编码
    assert info.has_audio


def test_probe_rejects_non_media(tmp_path, tools):
    _, ffprobe = tools
    fake = tmp_path / "not_video.mp4"
    fake.write_bytes(b"hello world")
    from app.media_info import MediaProbeError

    with pytest.raises(MediaProbeError):
        probe_media(fake, ffprobe)
