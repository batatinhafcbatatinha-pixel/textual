from __future__ import annotations

import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from textual.app import ComposeResult
from textual.color import Color
from textual.css.stylesheet import Stylesheet
from textual.widgets import Label, Static

from .test_graphics_compositor import DCS, RecordingApp, make_image, sixel_sizes


@pytest.fixture
def wallpaper(tmp_path) -> str:
    path = tmp_path / "wallpaper.png"
    make_image(400, 200).save(path)
    return str(path).replace("\\", "/")


@pytest.fixture
def sixel_terminal(monkeypatch):
    monkeypatch.setenv("TEXTUAL_GRAPHICS", "sixel")


def parse(css: str) -> dict:
    stylesheet = Stylesheet()
    stylesheet.add_source(css, read_from=("test", ""))
    stylesheet.parse()
    return dict(stylesheet.rules[0].styles._rules)


def test_css_background_image_properties():
    rules = parse('Screen { background-image: "a b.png"; background-image-fit: contain; }')
    assert rules["background_image"] == "a b.png"
    assert rules["background_image_fit"] == "contain"


def test_css_background_shorthand_with_image():
    rules = parse('Screen { background: #102030 "wall.png" fill; }')
    assert rules["background"] == Color(16, 32, 48)
    assert rules["background_image"] == "wall.png"
    assert rules["background_image_fit"] == "fill"


def test_css_background_color_alias():
    rules = parse("Screen { background-color: red 50%; }")
    assert rules["background"] == Color(255, 0, 0, 0.5)
    assert "background_image" not in parse("Screen { background: blue; }")


def make_app(wallpaper: str, css: str = "", widgets=()):
    class WallpaperApp(RecordingApp):
        CSS = f'Screen {{ background-image: "{wallpaper}"; }}\n{css}'

        def compose(self) -> ComposeResult:
            yield from widgets

    return WallpaperApp()


async def test_screen_background_written_once(sixel_terminal, wallpaper):
    app = make_app(
        wallpaper,
        "#opaque { background: red; width: 10; height: 1; }",
        [Label("hello world", id="label"), Static("opaque", id="opaque")],
    )
    async with app.run_test(size=(20, 6)) as pilot:
        await pilot.pause()
        frames = app.take_frames()
        assert sixel_sizes(frames) == [(200, 120)]
        assert frames.index(DCS) < frames.index("hello")

        # Updating an opaque widget doesn't touch the background
        app.query_one("#opaque", Static).update("changed")
        await pilot.pause()
        frames = app.take_frames()
        assert "changed" in frames
        assert DCS not in frames


async def test_background_shows_through_transparent_widgets(sixel_terminal, wallpaper):
    app = make_app(wallpaper, "", [Label("hello world", id="label")])
    async with app.run_test(size=(20, 6)) as pilot:
        await pilot.pause()
        app.take_frames()
        # Shorter text: the cells where "world" was must get the image back
        app.query_one("#label", Label).update("hi")
        await pilot.pause()
        frames = app.take_frames()
        assert "hi" in frames
        sizes = sixel_sizes(frames)
        assert sizes, "background must be repaired where text was erased"
        # Only the cells of the old text, not the whole screen
        assert all(height == 20 and width < 200 for width, height in sizes)


async def test_overlay_closing_restores_background(sixel_terminal, wallpaper):
    app = make_app(
        wallpaper,
        "#overlay { background: blue; width: 8; height: 3; offset: 2 1; }",
        [Static("menu", id="overlay")],
    )
    async with app.run_test(size=(20, 6)) as pilot:
        await pilot.pause()
        app.take_frames()
        app.query_one("#overlay").display = False
        await pilot.pause()
        frames = app.take_frames()
        assert sixel_sizes(frames) == [(80, 60)]


async def test_halfblock_background(monkeypatch, wallpaper):
    monkeypatch.setenv("TEXTUAL_GRAPHICS", "halfblock")
    app = make_app(wallpaper, "", [Label("hello", id="label")])
    async with app.run_test(size=(20, 6)) as pilot:
        await pilot.pause()
        frames = app.take_frames()
        assert DCS not in frames
        assert "▀" in frames
        assert "hello" in frames


async def test_widget_background_image(sixel_terminal, wallpaper):
    css = f'#panel {{ background-image: "{wallpaper}"; border: round red; width: 12; height: 5; }}'

    class PanelApp(RecordingApp):
        CSS = css

        def compose(self) -> ComposeResult:
            yield Static("", id="panel")

    app = PanelApp()
    async with app.run_test(size=(30, 8)) as pilot:
        await pilot.pause()
        # Inside the border: 10x3 cells
        assert sixel_sizes(app.take_frames()) == [(100, 60)]


async def test_missing_background_image(sixel_terminal):
    app = make_app("does/not/exist.png", "", [Label("hello")])
    async with app.run_test(size=(20, 6)) as pilot:
        await pilot.pause()
        frames = app.take_frames()
        assert DCS not in frames
        assert "hello" in frames
