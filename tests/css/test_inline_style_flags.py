from rich.style import Style

from textual.app import App, ComposeResult
from textual.widgets import Label


async def test_text_style_from_set_styles():
    """Regression test: `set_styles("text-style: ...")` stored a str instead of a Style."""

    class StyleApp(App):
        def compose(self) -> ComposeResult:
            label = Label("hello")
            label.set_styles("text-style: bold italic; border-title-style: underline;")
            yield label

    app = StyleApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        styles = app.query_one(Label).styles
        assert styles.text_style == Style(bold=True, italic=True)
        assert styles.border_title_style == Style(underline=True)
