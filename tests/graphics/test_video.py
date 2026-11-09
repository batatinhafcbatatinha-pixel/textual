from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path

import pytest

av = pytest.importorskip("av")
np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

from textual.app import App, ComposeResult
from textual.widgets import Video

from .test_graphics_compositor import DCS, RecordingApp, sixel_sizes


@pytest.fixture(scope="module")
def video_path(tmp_path_factory) -> Path:
    """A 1 second, 10 fps, 80x40 video with a silent audio track."""
    path = tmp_path_factory.mktemp("video") / "clip.mp4"
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=10)
        stream.width, stream.height, stream.pix_fmt = 80, 40, "yuv420p"
        audio = container.add_stream("aac", rate=8000)
        audio.layout = "mono"
        for index in range(10):
            pixels = np.full((40, 80, 3), index * 25, np.uint8)
            for packet in stream.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
        for start in range(0, 8000, 1024):
            frame = av.AudioFrame.from_ndarray(
                np.zeros((1, 1024), np.float32), format="fltp", layout="mono"
            )
            frame.sample_rate = 8000
            frame.pts = start
            frame.time_base = Fraction(1, 8000)
            for packet in audio.encode(frame):
                container.mux(packet)
        for packet in audio.encode():
            container.mux(packet)
    return path


async def wait_for(condition, timeout: float = 5.0) -> None:
    for _ in range(int(timeout / 0.02)):
        if condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("timed out")


async def test_video_plays_to_the_end(video_path, monkeypatch):
    monkeypatch.setenv("TEXTUAL_GRAPHICS", "sixel")
    finished: list[Video.Finished] = []

    class VideoApp(RecordingApp):
        CSS = "Video { width: 8; height: 2; }"

        def compose(self) -> ComposeResult:
            yield Video(video_path, autoplay=True, audio=False)

        def on_video_finished(self, event: Video.Finished) -> None:
            finished.append(event)

    app = VideoApp()
    async with app.run_test(size=(40, 10)) as pilot:
        video = app.query_one(Video)
        assert video.duration == pytest.approx(1.0, abs=0.2)
        await wait_for(lambda: finished)
        await pilot.pause()
        assert not video.playing
        frames = app.take_frames()
        # Several frames were written, each as a Sixel at the widget size
        sizes = sixel_sizes(frames)
        assert len(sizes) >= 3
        assert set(sizes) == {(80, 40)}


async def test_still_frame_and_seek(video_path):
    class VideoApp(App):
        CSS = "Video { width: 8; height: 2; }"

        def compose(self) -> ComposeResult:
            yield Video(video_path, render_mode="halfblock", audio=False)

    app = VideoApp()
    async with app.run_test(size=(40, 10)) as pilot:
        video = app.query_one(Video)
        await wait_for(lambda: video.get_frame() is not None)
        assert not video.playing
        first = np.asarray(video.get_frame()).mean()
        video.seek(0.8)
        await wait_for(lambda: np.asarray(video.get_frame()).mean() > first + 50)
        assert video.position == pytest.approx(0.8)


async def test_pause_and_resume(video_path):
    class VideoApp(App):
        def compose(self) -> ComposeResult:
            yield Video(video_path, audio=False)

    app = VideoApp()
    async with app.run_test(size=(40, 10)) as pilot:
        video = app.query_one(Video)
        await pilot.pause()
        video.play()
        assert video.playing
        await asyncio.sleep(0.3)
        video.pause()
        assert not video.playing
        paused_at = video.position
        assert 0.0 < paused_at < 1.0
        await asyncio.sleep(0.2)
        assert video.position == paused_at
        await pilot.press("space")
        assert video.playing


async def test_missing_video_shows_error():
    class VideoApp(RecordingApp):
        def compose(self) -> ComposeResult:
            yield Video("missing.mp4")

    app = VideoApp()
    async with app.run_test(size=(60, 10)) as pilot:
        await pilot.pause()
        assert "Unable to open video" in app.take_frames()
        assert DCS not in app.take_frames()
