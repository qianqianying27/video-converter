"""用 ffmpeg lavfi 生成一个演示用测试视频。

用法：python scripts/make_test_video.py [输出路径] [时长秒]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.env import resolve_tools, run_capture  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="生成测试视频")
    parser.add_argument("output", nargs="?", default="sample.mp4")
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()

    ffmpeg, _ = resolve_tools(None)
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(ffmpeg), "-hide_banner", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", str(args.seconds),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        str(out),
    ]
    cp = run_capture(cmd, timeout=300)
    if cp.returncode != 0:
        print(cp.stderr, file=sys.stderr)
        return cp.returncode
    print(f"已生成：{out}（{out.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
