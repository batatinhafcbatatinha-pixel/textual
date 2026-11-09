"""Image widget demo: scroll, resize, and overlays should not flicker.

Run with: python examples/media/image_demo.py [image ...]

Keys: f = cycle fit, r = toggle render mode (Sixel / half blocks).
"""

import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Image, Input, Label, Select

SAMPLE = Path(__file__).parent / "sample.png"


class ImageDemo(App):
    CSS = """
    #controls { height: auto; }
    #controls Select { width: 32; }
    #controls Input { width: 1fr; }
    VerticalScroll { padding: 0 1; }
    Horizontal { height: auto; }
    #hero { margin-top: 1; height: auto; }
    #logo { width: 16; }
    #intro { width: 1fr; height: auto; padding: 0 2; }
    #intro .title { text-style: bold; color: $accent; }
    .caption { margin-top: 1; text-style: bold; }
    .thumb { width: 26; height: 7; border: round $accent; margin-right: 1; }
    """
    BINDINGS = [("f", "cycle_fit", "Cycle fit"), ("r", "cycle_render", "Cycle render mode")]

    def __init__(self, images: list[str]) -> None:
        super().__init__()
        self.images = images or [str(SAMPLE)]

    def image(self, index: int = 0) -> str:
        return self.images[index % len(self.images)]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="controls"):
            yield Select(
                [(name, name) for name in ("One", "Two", "Three", "Four")],
                prompt="Open me over the images",
            )
            yield Input(placeholder="Type here: the images must not flicker")
        with VerticalScroll():
            with Horizontal(id="hero"):
                yield Image(self.image(), id="logo")
                with Vertical(id="intro"):
                    yield Label("Native Image widget", classes="title")
                    yield Label("Real pixels with Sixel, or colored half blocks.")
                    yield Label("Scroll, resize, open the menu: no flicker.")
            yield Label("fit = contain · cover · fill", classes="caption")
            with Horizontal():
                for fit in ("contain", "cover", "fill"):
                    image = Image(self.image(0), fit=fit, classes="thumb")
                    image.border_title = fit
                    yield image
            yield Label("render_mode = sixel · halfblock", classes="caption")
            with Horizontal():
                for mode in ("sixel", "halfblock"):
                    image = Image(self.image(1), render_mode=mode, classes="thumb")
                    image.border_title = mode
                    yield image
            for index in range(3):
                yield Label(f"Line of text {index}", classes="caption")
                yield Image(self.image(index), classes="thumb")
        yield Footer()

    def action_cycle_fit(self) -> None:
        for image in self.query(Image):
            image.fit = {"contain": "cover", "cover": "fill", "fill": "contain"}[image.fit]

    def action_cycle_render(self) -> None:
        for image in self.query(Image):
            image.render_mode = "halfblock" if image.uses_sixel else "sixel"


if __name__ == "__main__":
    ImageDemo(sys.argv[1:]).run()
