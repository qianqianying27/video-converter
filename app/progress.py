"""ffmpeg ``-progress pipe:1`` 输出解析。

ffmpeg 每个进度块是一组 ``key=value`` 行，以 ``progress=continue`` 或
``progress=end`` 结尾。这里把它解析成 :class:`ProgressInfo`：

- ``out_time_us`` / ``out_time_ms`` 单位为微秒（ffmpeg 的历史遗留命名）；
- 某些场景（如 ``-c copy``）可能没有时间字段，此时百分比为 None，
  UI 显示“处理中…”而不是卡在 0%。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TIME_RE = re.compile(r"^(\d+):(\d{2}):(\d{2}(?:\.\d+)?)$")


@dataclass(frozen=True)
class ProgressInfo:
    seconds: float = 0.0
    percent: float | None = None
    fps: float | None = None
    speed: float | None = None
    bitrate: str | None = None
    done: bool = False


def _to_seconds(fields: dict[str, str]) -> float:
    for key in ("out_time_us", "out_time_ms"):
        raw = fields.get(key)
        if raw:
            try:
                return max(0.0, float(raw) / 1_000_000.0)
            except ValueError:
                pass
    raw = fields.get("out_time")
    if raw:
        m = _TIME_RE.match(raw.strip())
        if m:
            h, mi, s = m.groups()
            return int(h) * 3600 + int(mi) * 60 + float(s)
    return 0.0


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class ProgressParser:
    """逐行喂入；每次遇到 ``progress=`` 行时返回一条 :class:`ProgressInfo`。"""

    def __init__(self, duration: float | None = None) -> None:
        self._duration = duration if duration and duration > 0 else None
        self._fields: dict[str, str] = {}

    def feed(self, line: str) -> ProgressInfo | None:
        line = line.strip()
        if not line or "=" not in line:
            return None
        key, _, value = line.partition("=")
        if key == "progress":
            info = self._build(done=(value.strip() == "end"))
            self._fields = {}
            return info
        self._fields[key.strip()] = value.strip()
        return None

    def _build(self, *, done: bool) -> ProgressInfo:
        seconds = _to_seconds(self._fields)
        percent = None
        if self._duration:
            percent = min(100.0, max(0.0, seconds / self._duration * 100.0))
            if done:
                percent = 100.0
        speed = _to_float(self._fields.get("speed", "").rstrip("x"))
        return ProgressInfo(
            seconds=seconds,
            percent=percent,
            fps=_to_float(self._fields.get("fps")),
            speed=speed,
            bitrate=self._fields.get("bitrate") or None,
            done=done,
        )
