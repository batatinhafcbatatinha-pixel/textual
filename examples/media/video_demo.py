"""Video widget demo.

Run with: python examples/media/video_demo.py [video]

Keys: space = play/pause, left/right = seek, m = mute, f = cycle fit, l = loop.
Options: --mute starts muted, --loop loops.
"""

import sys
from pathlib import Path
from time import monotonic

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Label, ProgressBar, Video

SAMPLE = Path(__file__).parent / "sample.mp4"


class VideoDemo(App):
    CSS = """
    Vertical { align: center middle; }
    Video { width: 90%; height: 1fr; border: round $accent; }
    #status { width: 90%; height: 1; }
    ProgressBar { width: 90%; }
    """
    BINDINGS = [("f", "cycle_fit", "Cycle fit"), ("l", "toggle_loop", "Loop")]

    def __init__(self, path: str, muted: bool = False) -> None:
        super().__init__()
        self.path = path
        self.muted = muted

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Video(self.path, autoplay=True)
            yield ProgressBar(show_eta=False, show_percentage=False)
            yield Label(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Video).muted = self.muted
        self.query_one(Video).loop = getattr(self, "loop", False)
        self._last_frames = (0, 0.0)
        self.fps = 0.0
        self.set_interval(0.5, self.update_status)

    def update_status(self) -> None:
        video = self.query_one(Video)
        frames, last_time = self._last_frames
        now = monotonic()
        if last_time:
            self.fps = (video.frames_shown - frames) / (now - last_time)
        self._last_frames = (video.frames_shown, now)
        bar = self.query_one(ProgressBar)
        bar.update(total=video.duration or None, progress=video.position)
        state = "▶" if video.playing else "⏸"
        mute = " 🔇" if video.muted else ""
        self.query_one("#status", Label).update(
            f"{state} {video.position:6.1f}s / {video.duration:.1f}s  fit={video.fit}"
            f"  loop={video.loop}{mute}  {self.fps:4.1f} fps"
            f"  shown={video.frames_shown} dropped={video.frames_dropped}"
        )

    def action_cycle_fit(self) -> None:
        video = self.query_one(Video)
        video.fit = {"contain": "cover", "cover": "fill", "fill": "contain"}[video.fit]

    def action_toggle_loop(self) -> None:
        video = self.query_one(Video)
        video.loop = not video.loop


if __name__ == "__main__":
    args = [arg for arg in sys.argv[1:] if arg != "--mute"]
    args = [arg for arg in args if arg != "--loop"]
    app = VideoDemo(args[0] if args else str(SAMPLE), muted="--mute" in sys.argv)
    app.loop = "--loop" in sys.argv
    app.run()
