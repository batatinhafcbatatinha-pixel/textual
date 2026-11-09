"""Background image demo: `background-image` on the Screen and on a panel.

Run with: python examples/media/background_demo.py [image]

Transparent widgets (like Label) show the image behind them; opaque widgets
(like Input) cover it. Keys: f = cycle fit, b = toggle the screen background.
"""

import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Label, Select

SAMPLE = Path(__file__).parent / "sample.png"


class BackgroundDemo(App):
    CSS = """
    Screen { align: center middle; }
    #card {
        width: 50;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $panel 60%;
    }
    #card Label { width: 100%; content-align: center middle; text-style: bold; }
    #thumb {
        width: 24;
        height: 8;
        margin-top: 1;
        border: round $secondary;
        background-image-fit: contain;
    }
    Select, Input { margin-top: 1; }
    """
    BINDINGS = [("f", "cycle_fit", "Cycle fit"), ("b", "toggle_background", "Toggle background")]

    def __init__(self, image: str) -> None:
        super().__init__()
        self.image = image

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="card"):
            yield Label("Background image with background-image")
            yield Select([(name, name) for name in ("One", "Two", "Three")], prompt="Open me over the image")
            yield Input(placeholder="Type here (the background must not flicker)")
            yield Label("Panel with its own image:")
            yield Vertical(id="thumb")
        yield Footer()

    def on_mount(self) -> None:
        self.screen.styles.background_image = self.image
        self.query_one("#thumb").styles.background_image = self.image

    def action_cycle_fit(self) -> None:
        styles = self.screen.styles
        styles.background_image_fit = {"cover": "contain", "contain": "fill", "fill": "cover"}[
            styles.background_image_fit
        ]
        self.notify(f"fit = {styles.background_image_fit}")

    def action_toggle_background(self) -> None:
        styles = self.screen.styles
        styles.background_image = "none" if styles.background_image != "none" else self.image


if __name__ == "__main__":
    BackgroundDemo(sys.argv[1] if len(sys.argv) > 1 else str(SAMPLE)).run()
