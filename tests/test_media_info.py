"""单元测试：ffprobe JSON 解析（不依赖 ffmpeg）。"""

from pathlib import Path

from app.media_info import (
    human_bitrate,
    human_duration,
    human_size,
    parse_ffprobe_json,
)

SAMPLE = {
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "pix_fmt": "yuv420p",
            "avg_frame_rate": "30000/1001",
            "r_frame_rate": "60/1",
            "bit_rate": "4000000",
        },
        {
            "codec_type": "audio",
            "codec_name": "aac",
            "channels": 2,
            "sample_rate": "48000",
        },
    ],
    "format": {"duration": "12.345", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
}


def test_parse_basic_metadata():
    info = parse_ffprobe_json(SAMPLE, Path("a.mp4"), 12345)
    assert info.container == "mov"
    assert info.duration == 12.345
    assert info.width == 1920
    assert info.height == 1080
    assert info.has_video and info.has_audio
    assert abs(info.fps - 29.97) < 0.01
    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert info.audio_channels == 2
    assert info.audio_rate == 48000
    assert info.size_bytes == 12345


def test_rotation_swaps_width_height():
    data = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "hevc",
                "width": 1920,
                "height": 1080,
                "tags": {"rotate": "90"},
            }
        ],
        "format": {"duration": "1.0", "format_name": "matroska,webm"},
    }
    info = parse_ffprobe_json(data, Path("b.mkv"), 1)
    assert info.rotation == 90
    assert (info.width, info.height) == (1080, 1920)


def test_audio_only_file():
    data = {
        "streams": [{"codec_type": "audio", "codec_name": "mp3", "channels": 1,
                     "sample_rate": "44100"}],
        "format": {"duration": "3.0", "format_name": "mp3"},
    }
    info = parse_ffprobe_json(data, Path("c.mp3"), 10)
    assert not info.has_video
    assert info.has_audio
    assert info.resolution == "—"
    assert info.video_codec == ""


def test_attached_picture_is_not_video_stream():
    data = {
        "streams": [
            {"codec_type": "video", "codec_name": "mjpeg",
             "disposition": {"attached_pic": 1}, "width": 600, "height": 600},
            {"codec_type": "audio", "codec_name": "mp3", "channels": 2, "sample_rate": "44100"},
        ],
        "format": {"duration": "2.0", "format_name": "mp3"},
    }
    info = parse_ffprobe_json(data, Path("d.mp3"), 10)
    assert not info.has_video


def test_human_formatters():
    assert human_duration(0) == "00:00"
    assert human_duration(65) == "01:05"
    assert human_duration(3661) == "01:01:01"
    assert human_size(512) == "512 B"
    assert human_size(1536) == "1.5 KB"
    assert human_size(1024 * 1024) == "1.0 MB"
    assert human_bitrate(1_500_000) == "1.50 Mbps"
    assert human_bitrate(128_000) == "128 kbps"
    assert human_bitrate(0) == "—"
