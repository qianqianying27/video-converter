"""单元测试：ffmpeg -progress 输出解析。"""

from app.progress import ProgressParser


def test_out_time_us_gives_percent():
    parser = ProgressParser(duration=10.0)
    assert parser.feed("frame=42") is None
    assert parser.feed("out_time_us=2500000") is None
    info = parser.feed("progress=continue")
    assert info is not None
    assert info.seconds == 2.5
    assert info.percent == 25.0
    assert info.done is False


def test_progress_end_forces_100_percent():
    parser = ProgressParser(duration=10.0)
    parser.feed("out_time_us=1000000")
    info = parser.feed("progress=end")
    assert info.done is True
    assert info.percent == 100.0


def test_out_time_ms_fallback():
    parser = ProgressParser(duration=4.0)
    parser.feed("out_time_ms=2000000")  # ffmpeg 的 out_time_ms 实际是微秒
    info = parser.feed("progress=continue")
    assert info.seconds == 2.0
    assert info.percent == 50.0


def test_out_time_string_fallback():
    parser = ProgressParser(duration=60.0)
    parser.feed("out_time=00:00:05.500000")
    info = parser.feed("progress=continue")
    assert info.seconds == 5.5


def test_no_duration_means_unknown_percent():
    parser = ProgressParser(duration=0)
    parser.feed("out_time_us=5000000")
    info = parser.feed("progress=continue")
    assert info.percent is None


def test_speed_and_fps_parsed():
    parser = ProgressParser(duration=10.0)
    parser.feed("fps=29.97")
    parser.feed("speed=2.1x")
    info = parser.feed("progress=continue")
    assert info.fps == 29.97
    assert info.speed == 2.1


def test_garbage_lines_ignored():
    parser = ProgressParser(duration=5.0)
    assert parser.feed("") is None
    assert parser.feed("没有等号") is None
    assert parser.feed("progress=continue") is not None
