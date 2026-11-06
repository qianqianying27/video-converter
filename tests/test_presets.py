"""单元测试：转码预设与命令行构建（不依赖 ffmpeg）。"""

from pathlib import Path

from app.presets import (
    Preset,
    build_args,
    get_preset,
    output_path,
    parse_crf,
    parse_height,
    scale_filter,
)

FFMPEG = Path("ffmpeg")
SRC = Path("input.mov")


def _args(preset_key: str, dst: Path | None = None, **kwargs) -> list[str]:
    dst = dst or Path(f"out{get_preset(preset_key).ext}")
    return build_args(FFMPEG, get_preset(preset_key), SRC, dst, **kwargs)


def test_mp4_h264_args():
    args = _args("mp4", height=720, crf=20)
    joined = " ".join(args)
    assert "-c:v libx264" in joined
    assert "-crf 20" in joined
    assert "-vf scale=-2:720:flags=lanczos" in joined
    assert "-movflags +faststart" in joined
    assert str(SRC) in joined
    assert args[-1] == "out.mp4"


def test_webm_vp9_args():
    joined = " ".join(_args("webm", crf=30))
    assert "libvpx-vp9" in joined
    assert "libopus" in joined
    assert "-b:v 0" in joined


def test_mkv_copy_does_not_reencode():
    joined = " ".join(_args("mkv"))
    assert "-c copy" in joined
    assert "-c:v" not in joined


def test_gif_args():
    joined = " ".join(_args("gif"))
    assert "fps=12" in joined
    assert "scale=480:-2" in joined
    assert "-an" in joined
    assert "-loop 0" in joined


def test_mp3_args():
    joined = " ".join(_args("mp3"))
    assert "-vn" in joined
    assert "libmp3lame" in joined


def test_progress_pipe_enabled():
    joined = " ".join(_args("mp4"))
    assert "-progress pipe:1" in joined
    assert "-nostats" in joined


def test_output_path_collision(tmp_path: Path):
    preset = get_preset("mp4")
    src = tmp_path / "movie.mkv"
    src.write_bytes(b"x")
    first = output_path(src, preset, tmp_path)
    assert first.name == "movie_mp4.mp4"
    first.write_bytes(b"x")
    second = output_path(src, preset, tmp_path)
    assert second.name == "movie_mp4_2.mp4"


def test_parse_height():
    assert parse_height("720p") == 720
    assert parse_height("1080p") == 1080
    assert parse_height("保持原分辨率") is None
    assert parse_height("abc") is None
    assert parse_height("9999p") is None


def test_parse_crf_clamped():
    assert parse_crf("23") == 23
    assert parse_crf("-5") == 0
    assert parse_crf("99") == 51
    assert parse_crf("bad") == 23


def test_scale_filter_even_width():
    assert scale_filter(720) == "scale=-2:720:flags=lanczos"


def test_unknown_preset_raises():
    try:
        get_preset("nope")
    except KeyError:
        pass
    else:
        raise AssertionError("应当抛出 KeyError")


def test_preset_is_hashable_dataclass():
    p = Preset("x", "X", ".x")
    assert p.kind == "video"
