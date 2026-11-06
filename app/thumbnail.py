"""缩略图抽取。

策略：按 10% → 50% → 0% 的时间点依次抽帧，任何一次成功即返回；
全部失败才抛异常（由 UI 显示占位图）。抽取在后台线程执行，不阻塞界面。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .env import ensure_thumbnail_dir, run_capture

FALLBACK_FRACTIONS = (0.10, 0.50, 0.0)


class ThumbnailError(RuntimeError):
    """所有时间点都抽帧失败。"""


def cache_key(video_path: Path) -> str:
    raw = f"{video_path.resolve()}|{video_path.stat().st_mtime_ns}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def extract_thumbnail(
    ffmpeg: Path,
    src: Path,
    duration: float,
    *,
    max_width: int = 480,
    use_cache: bool = True,
) -> Path:
    """抽取代表性帧并保存为 JPEG，返回图片路径。

    Raises:
        ThumbnailError: 所有回退时间点都失败
    """
    cache_dir = ensure_thumbnail_dir()
    dest = cache_dir / f"{cache_key(src)}.jpg"
    if use_cache and dest.exists() and dest.stat().st_size > 0:
        return dest

    errors: list[str] = []
    for fraction in FALLBACK_FRACTIONS:
        t = max(0.0, duration * fraction)
        args = [
            str(ffmpeg), "-hide_banner", "-y",
            "-ss", f"{t:.3f}",
            "-i", str(src),
            "-frames:v", "1",
            "-vf", f"scale={max_width}:-2:force_original_aspect_ratio=decrease:flags=lanczos",
            "-q:v", "3",
            str(dest),
        ]
        try:
            cp = run_capture(args, timeout=60)
        except Exception as exc:
            errors.append(f"@{fraction:.0%}: {exc}")
            continue
        if cp.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return dest
        errors.append(f"@{fraction:.0%}: {(cp.stderr or '').strip()[-200:]}")

    detail = "; ".join(errors)
    raise ThumbnailError(f"无法生成缩略图（{detail}）")
