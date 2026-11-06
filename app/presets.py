"""转码预设与 ffmpeg 命令行构建。

设计要点：
- 预设只描述“目标是什么”，命令行细节集中在 :func:`build_args`；
- 构建逻辑纯函数、无副作用，可单测；
- 不带 shell 执行（列表参数），避免路径含空格/中文时的转义问题。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CRF_MIN, CRF_MAX, CRF_DEFAULT = 0, 51, 23


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    ext: str
    kind: str = "video"          # video | copy | audio | gif
    video_codec: str = ""
    audio_codec: str = ""
    note: str = ""


PRESETS: tuple[Preset, ...] = (
    Preset("mp4", "MP4（H.264）", ".mp4", "video", "libx264", "aac",
           "兼容性最好，体积与画质平衡"),
    Preset("mkv", "MKV（无损换封装）", ".mkv", "copy", "", "",
           "不重新编码，秒级完成；要求源编码被 MKV 支持"),
    Preset("webm", "WebM（VP9）", ".webm", "video", "libvpx-vp9", "libopus",
           "网页友好，同画质体积更小，编码较慢"),
    Preset("gif", "GIF 动图", ".gif", "gif", "", "",
           "固定 12fps、宽 480，适合做表情包/预览图"),
    Preset("mp3", "MP3 音频", ".mp3", "audio", "", "libmp3lame",
           "只提取音轨，不保留画面"),
)

PRESETS_BY_KEY: dict[str, Preset] = {p.key: p for p in PRESETS}


def get_preset(key: str) -> Preset:
    try:
        return PRESETS_BY_KEY[key]
    except KeyError as exc:
        raise KeyError(f"未知的格式预设：{key}") from exc


def scale_filter(height: int) -> str:
    """按目标高度等比缩放（宽度自动、保证偶数，适配 H.264 要求）。"""
    return f"scale=-2:{int(height)}:flags=lanczos"


def build_args(
    ffmpeg: Path,
    preset: Preset,
    src: Path,
    dst: Path,
    *,
    crf: int = CRF_DEFAULT,
    height: int | None = None,
    fps: float | None = None,
) -> list[str]:
    """构建 ffmpeg 参数列表。

    Args:
        height: 目标高度（px）；None 表示保持原分辨率
        fps:    目标帧率；None 表示保持原帧率
        crf:    质量参数（0 最好、51 最差），对 libx264 / libvpx-vp9 生效
    """
    args: list[str] = [
        str(ffmpeg),
        "-hide_banner", "-y",
        "-i", str(src),
        "-progress", "pipe:1", "-nostats",
        "-loglevel", "error",
    ]

    if preset.kind == "gif":
        args += ["-an", "-vf", "fps=12,scale=480:-2:flags=lanczos", "-loop", "0"]

    elif preset.kind == "audio":
        args += ["-vn", "-c:a", preset.audio_codec or "libmp3lame", "-q:a", "2"]

    elif preset.kind == "copy":
        args += ["-c", "copy"]

    else:  # video re-encode
        filters: list[str] = []
        if height:
            filters.append(scale_filter(height))
        if filters:
            args += ["-vf", ",".join(filters)]
        if fps:
            args += ["-r", str(fps)]

        if preset.video_codec == "libx264":
            args += [
                "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            ]
            args += ["-c:a", "aac", "-b:a", "160k"]
        elif preset.video_codec == "libvpx-vp9":
            args += [
                "-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0",
                "-row-mt", "1", "-c:a", preset.audio_codec or "libopus",
                "-b:a", "96k",
            ]
        else:  # 兜底：交给 ffmpeg 选择同容器默认编码器
            args += ["-c:v", preset.video_codec or "libx264"]

    args.append(str(dst))
    return args


def output_path(src: Path, preset: Preset, out_dir: Path) -> Path:
    """生成不冲突的输出文件名：<原名>_<预设>.<扩展名>。"""
    base = f"{src.stem}_{preset.key}"
    candidate = out_dir / f"{base}{preset.ext}"
    index = 2
    while candidate.exists():
        candidate = out_dir / f"{base}_{index}{preset.ext}"
        index += 1
    return candidate


def parse_crf(text: str, default: int = CRF_DEFAULT) -> int:
    try:
        value = int(float(text))
    except (TypeError, ValueError):
        return default
    return max(CRF_MIN, min(CRF_MAX, value))


def parse_height(text: str) -> int | None:
    """'720p' / '720' / '保持原分辨率' -> 720 / None。"""
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    value = int(digits)
    return value if 100 <= value <= 4320 else None
