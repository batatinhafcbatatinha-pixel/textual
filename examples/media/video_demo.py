"""Video widget demo.

Run with: python examples/media/video_demo.py [video]

Keys: space = play/pause, left/right = seek, m = mute, f = cycle fit.
"""

import sys
from pathlib import Path

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

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Video(self.path, autoplay=True)
            yield ProgressBar(show_eta=False, show_percentage=False)
            yield Label(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.2, self.update_status)

    def update_status(self) -> None:
        video = self.query_one(Video)
        bar = self.query_one(ProgressBar)
        bar.update(total=video.duration or None, progress=video.position)
        state = "▶" if video.playing else "⏸"
        mute = " 🔇" if video.muted else ""
        self.query_one("#status", Label).update(
            f"{state} {video.position:6.1f}s / {video.duration:.1f}s  fit={video.fit}"
            f"  loop={video.loop}{mute}"
        )

    def action_cycle_fit(self) -> None:
        video = self.query_one(Video)
        video.fit = {"contain": "cover", "cover": "fill", "fill": "contain"}[video.fit]

    def action_toggle_loop(self) -> None:
        video = self.query_one(Video)
        video.loop = not video.loop


if __name__ == "__main__":
    VideoDemo(sys.argv[1] if len(sys.argv) > 1 else str(SAMPLE)).run()
