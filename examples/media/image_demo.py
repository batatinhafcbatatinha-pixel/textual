"""Image widget demo: scroll, resize, and overlays should not flicker.

Run with: python examples/media/image_demo.py [image ...]
"""

import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Image, Input, Label, Select

SAMPLE = Path(__file__).parent / "sample.png"


class ImageDemo(App):
    CSS = """
    VerticalScroll { padding: 0 1; }
    Horizontal { height: auto; }
    #big { width: 60; }
    .thumb { width: 24; height: 8; border: round $accent; margin-right: 1; }
    .cover { width: 1fr; height: 10; }
    Select { width: 30; }
    """
    BINDINGS = [("f", "cycle_fit", "Cycle fit"), ("r", "cycle_render", "Cycle render mode")]

    def __init__(self, images: list[str]) -> None:
        super().__init__()
        self.images = images or [str(SAMPLE)]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Select([(name, name) for name in ("One", "Two", "Three", "Four")], prompt="Open me over the image")
            yield Input(placeholder="Type here (the image must not flicker)")
        with VerticalScroll():
            yield Image(self.images[0], id="big")
            yield Label("Scroll down ↓ and resize the window.")
            with Horizontal():
                for index in range(4):
                    yield Image(self.images[index % len(self.images)], classes="thumb")
            yield Label("fit=cover:")
            yield Image(self.images[-1], fit="cover", classes="cover")
            for index in range(3):
                yield Label(f"Line of text {index}")
                yield Image(self.images[index % len(self.images)])
        yield Footer()

    def action_cycle_fit(self) -> None:
        for image in self.query(Image):
            image.fit = {"contain": "cover", "cover": "fill", "fill": "contain"}[image.fit]

    def action_cycle_render(self) -> None:
        for image in self.query(Image):
            image.render_mode = "halfblock" if image.uses_sixel else "sixel"


if __name__ == "__main__":
    ImageDemo(sys.argv[1:]).run()
