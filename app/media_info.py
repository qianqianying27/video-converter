"""视频元信息探测（ffprobe）。

对外只暴露 :func:`probe_media`；解析逻辑拆到 :func:`parse_ffprobe_json`，
便于脱离 ffmpeg 做单元测试。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .env import run_capture


class MediaProbeError(RuntimeError):
    """ffprobe 执行失败或输出无法解析。"""


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    size_bytes: int
    container: str
    duration: float          # 秒
    width: int
    height: int
    fps: float
    video_codec: str
    pixel_format: str
    rotation: int
    video_bitrate: int
    audio_codec: str
    audio_channels: int
    audio_rate: int
    has_video: bool
    has_audio: bool

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}" if self.width and self.height else "—"

    @property
    def is_rotated(self) -> bool:
        return self.rotation % 180 != 0


def _parse_fraction(value: str | None) -> float:
    """'30000/1001' -> 29.97；异常值返回 0。"""
    if not value or value in ("0/0", "N/A"):
        return 0.0
    try:
        if "/" in value:
            num, den = value.split("/", 1)
            den_f = float(den)
            return float(num) / den_f if den_f else 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_rotation(stream: dict) -> int:
    tags = stream.get("tags") or {}
    raw = tags.get("rotate")
    if raw is not None:
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            pass
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            try:
                return int(float(side["rotation"]))
            except (TypeError, ValueError):
                pass
    return 0


def parse_ffprobe_json(data: dict, path: Path, size_bytes: int) -> VideoInfo:
    streams = data.get("streams") or []
    fmt = data.get("format") or {}

    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = 0.0
    for src in (fmt.get("duration"), (video or {}).get("duration")):
        try:
            duration = float(src)
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue

    width = int(video.get("width") or 0) if video else 0
    height = int(video.get("height") or 0) if video else 0
    rotation = _parse_rotation(video) if video else 0
    if rotation % 180 != 0:  # 旋转 90/270 度时宽高互换
        width, height = height, width

    return VideoInfo(
        path=path,
        size_bytes=size_bytes,
        container=(fmt.get("format_name") or "").split(",")[0],
        duration=max(duration, 0.0),
        width=width,
        height=height,
        fps=_parse_fraction((video or {}).get("avg_frame_rate")
                            or (video or {}).get("r_frame_rate")),
        video_codec=(video or {}).get("codec_name") or "",
        pixel_format=(video or {}).get("pix_fmt") or "",
        rotation=rotation,
        video_bitrate=int((video or {}).get("bit_rate") or 0),
        audio_codec=(audio or {}).get("codec_name") or "",
        audio_channels=int((audio or {}).get("channels") or 0),
        audio_rate=int((audio or {}).get("sample_rate") or 0),
        has_video=video is not None,
        has_audio=audio is not None,
    )


def probe_media(path: Path, ffprobe: Path) -> VideoInfo:
    """调用 ffprobe 读取视频信息。

    Raises:
        MediaProbeError: 文件不可读 / 非媒体文件
    """
    cmd = [
        str(ffprobe), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        cp = run_capture(cmd, timeout=60)
    except Exception as exc:  # OSError / TimeoutExpired
        raise MediaProbeError(f"ffprobe 调用失败：{exc}") from exc
    if cp.returncode != 0:
        detail = (cp.stderr or "").strip().splitlines()
        raise MediaProbeError(detail[-1] if detail else "无法读取该文件（ffprobe 返回错误）")
    try:
        data = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("ffprobe 输出不是合法 JSON") from exc
    try:
        return parse_ffprobe_json(data, path, path.stat().st_size)
    except OSError as exc:
        raise MediaProbeError(f"读取文件大小失败：{exc}") from exc


# ---------- 展示格式化 ----------

def human_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def human_size(n: int) -> str:
    size = float(max(0, n))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def human_bitrate(bps: int) -> str:
    if bps <= 0:
        return "—"
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} Mbps"
    return f"{bps / 1000:.0f} kbps"
