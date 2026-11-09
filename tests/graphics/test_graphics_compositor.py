from __future__ import annotations

import re

import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from PIL import Image as PILImage

from textual import messages
from textual._compositor import CompositorUpdate
from textual._graphics import GRAPHICS_CHAR
from textual._xterm_parser import XTermParser
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Image, Label

DCS = "\x1bP"


def make_image(width: int = 120, height: int = 80) -> PILImage.Image:
    image = PILImage.new("RGB", (width, height), (200, 30, 30))
    image.paste((30, 200, 30), (0, 0, width // 2, height // 2))
    return image


class RecordingApp(App):
    """Records the terminal sequences of every compositor update."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.frames: list[str] = []

    def _display(self, screen, renderable) -> None:
        if isinstance(renderable, CompositorUpdate):
            self.frames.append(renderable.render_segments(self.console))
        super()._display(screen, renderable)

    def take_frames(self) -> str:
        frames = "".join(self.frames)
        self.frames.clear()
        return frames


@pytest.fixture
def sixel_terminal(monkeypatch):
    monkeypatch.setenv("TEXTUAL_GRAPHICS", "sixel")


def sixel_sizes(frames: str) -> list[tuple[int, int]]:
    return [
        (int(width), int(height))
        for width, height in re.findall(r'\x1bP0;1;0q"1;1;(\d+);(\d+)', frames)
    ]


async def test_sixel_written_once_and_cells_skipped(sixel_terminal):
    class ImageApp(RecordingApp):
        CSS = "Image { width: 12; height: 4; }"

        def compose(self) -> ComposeResult:
            yield Image(make_image())
            yield Label("hello", id="label")

    app = ImageApp()
    async with app.run_test(size=(40, 10)) as pilot:
        await pilot.pause()
        frames = app.take_frames()
        assert sixel_sizes(frames) == [(120, 80)]
        assert GRAPHICS_CHAR not in frames
        assert "\x1b[12C" in frames
        # The image is written before the text of the frame
        assert frames.index(DCS) < frames.index("hello")

        # Updating another widget must not write the image again
        app.query_one("#label", Label).update("world")
        await pilot.pause()
        frames = app.take_frames()
        assert "world" in frames
        assert DCS not in frames


async def test_new_image_is_written(sixel_terminal):
    class ImageApp(RecordingApp):
        CSS = "Image { width: 12; height: 4; }"

        def compose(self) -> ComposeResult:
            yield Image(make_image())

    app = ImageApp()
    async with app.run_test(size=(40, 10)) as pilot:
        await pilot.pause()
        app.take_frames()
        app.query_one(Image).image = make_image(60, 40)
        await pilot.pause()
        assert sixel_sizes(app.take_frames()) == [(120, 80)]


async def test_scroll_crops_and_erases(sixel_terminal):
    class ScrollApp(RecordingApp):
        CSS = """
        VerticalScroll { height: 10; scrollbar-size: 0 0; }
        Image { width: 10; height: 6; }
        Label { height: 20; }
        """

        def compose(self) -> ComposeResult:
            with VerticalScroll():
                yield Label("top")
                yield Image(make_image())
                yield Label("bottom")

    app = ScrollApp()
    async with app.run_test(size=(30, 10)) as pilot:
        await pilot.pause()
        app.take_frames()
        scroll = app.query_one(VerticalScroll)

        # Image covers lines 20-25; the viewport is 10 lines high.
        scroll.scroll_to(y=13, animate=False)
        await pilot.pause()
        # Partially visible at the bottom: lines 20-22
        assert sixel_sizes(app.take_frames()) == [(100, 60)]

        scroll.scroll_to(y=17, animate=False)
        await pilot.pause()
        assert sixel_sizes(app.take_frames()) == [(100, 120)]

        scroll.scroll_to(y=22, animate=False)
        await pilot.pause()
        # Partially visible at the top: lines 22-25
        assert sixel_sizes(app.take_frames()) == [(100, 80)]

        # Scrolled away: nothing to write, and the old area is redrawn with text
        scroll.scroll_to(y=40, animate=False)
        await pilot.pause()
        frames = app.take_frames()
        assert DCS not in frames
        assert frames


async def test_halfblock_mode():
    class ImageApp(RecordingApp):
        CSS = "Image { width: 12; height: 4; }"

        def compose(self) -> ComposeResult:
            yield Image(make_image(), render_mode="halfblock")

    app = ImageApp()
    async with app.run_test(size=(40, 10)) as pilot:
        await pilot.pause()
        frames = app.take_frames()
        assert DCS not in frames
        assert "▀" in frames


async def test_auto_size(sixel_terminal):
    class ImageApp(RecordingApp):
        def compose(self) -> ComposeResult:
            yield Image(make_image(100, 60))

    app = ImageApp()
    async with app.run_test(size=(40, 10)):
        image = app.query_one(Image)
        assert image.size == (10, 3)


async def test_missing_file_shows_error():
    class ImageApp(RecordingApp):
        def compose(self) -> ComposeResult:
            yield Image("does-not-exist.png")

    app = ImageApp()
    async with app.run_test(size=(60, 10)) as pilot:
        await pilot.pause()
        assert "Unable to load image" in app.take_frames()


def test_parse_device_attributes():
    parser = XTermParser()
    tokens = list(parser.feed("\x1b[?61;4;6;7;14;21;22;23;24;28;32;42;52c"))
    assert len(tokens) == 1
    assert isinstance(tokens[0], messages.TerminalGraphicsInfo)
    assert tokens[0].sixel is True

    tokens = list(XTermParser().feed("\x1b[?62;22c"))
    assert tokens[0].sixel is False


def test_parse_cell_size():
    tokens = list(XTermParser().feed("\x1b[6;20;10t"))
    assert len(tokens) == 1
    assert tokens[0].cell_size == (10, 20)


async def test_graphics_info_message_switches_to_sixel():
    class ImageApp(RecordingApp):
        CSS = "Image { width: 12; height: 4; }"

        def compose(self) -> ComposeResult:
            yield Image(make_image())

    app = ImageApp()
    async with app.run_test(size=(40, 10)) as pilot:
        await pilot.pause()
        assert DCS not in app.take_frames()
        app.post_message(messages.TerminalGraphicsInfo(sixel=True, cell_size=(8, 16)))
        await pilot.pause()
        await pilot.pause()
        assert sixel_sizes(app.take_frames()) == [(96, 64)]


async def test_forced_halfblock_ignores_terminal_report(monkeypatch):
    monkeypatch.setenv("TEXTUAL_GRAPHICS", "halfblock")

    class ImageApp(RecordingApp):
        CSS = "Image { width: 12; height: 4; }"

        def compose(self) -> ComposeResult:
            yield Image(make_image())

    app = ImageApp()
    async with app.run_test(size=(40, 10)) as pilot:
        app.post_message(messages.TerminalGraphicsInfo(sixel=True))
        await pilot.pause()
        await pilot.pause()
        assert not app.graphics_info.sixel
        assert DCS not in app.take_frames()
