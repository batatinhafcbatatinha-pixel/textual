"""Base class for widgets which display pixels (images, video)."""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

from rich.segment import Segment
from rich.style import Style

from textual._graphics import (
    Fit,
    RenderMode,
    fit_image,
    graphics_strip,
    halfblock_strips,
)
from textual.cache import LRUCache
from textual.geometry import Region, Size
from textual.reactive import reactive
from textual.strip import Strip
from textual.widget import Widget

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

MEDIA_INSTALL_HINT = "pip install textual[media]"


class GraphicsWidget(Widget):
    """A widget which displays pixels.

    Uses Sixel when the terminal supports it (or when `render_mode="sixel"`),
    and colored half blocks otherwise. Subclasses implement `get_frame`, and call
    `graphics_changed` when the frame changes.
    """

    DEFAULT_CSS = """
    GraphicsWidget {
        width: auto;
        height: auto;
        overflow: hidden hidden;
    }
    """

    fit: reactive[Fit] = reactive("contain")
    """How the frame is scaled: "contain", "cover", or "fill"."""

    render_mode: reactive[RenderMode] = reactive("auto")
    """How the frame is drawn: "auto", "sixel", or "halfblock"."""

    def __init__(
        self,
        *,
        fit: Fit = "contain",
        render_mode: RenderMode = "auto",
        colors: int = 256,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """
        Args:
            fit: How the frame is scaled: "contain", "cover", or "fill".
            render_mode: "auto", "sixel", or "halfblock".
            colors: Maximum number of colors per Sixel image (2-256).
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: The CSS classes of the widget.
            disabled: Whether the widget is disabled or not.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._graphics_generation = 0
        self._graphics_error: str | None = None
        self.sixel_colors = colors
        self._scaled_cache: LRUCache[tuple, PILImage] = LRUCache(4)
        self._sixel_cache: LRUCache[tuple, str] = LRUCache(16)
        self._halfblock_cache: tuple[tuple, list[Strip]] | None = None
        self.set_reactive(GraphicsWidget.fit, fit)
        self.set_reactive(GraphicsWidget.render_mode, render_mode)

    # -- API for subclasses -------------------------------------------------

    def get_frame(self) -> PILImage | None:
        """Get the frame (image) to display.

        Returns:
            A Pillow image, or `None` for nothing.
        """
        return None

    def get_frame_size(self) -> tuple[int, int] | None:
        """Get the natural size of the frame in pixels (used for `auto` dimensions)."""
        frame = self.get_frame()
        return None if frame is None else frame.size

    def graphics_changed(self, layout: bool = False) -> None:
        """Call when the frame changed, to redraw the widget.

        Args:
            layout: Also update the layout (when the natural size changed).
        """
        self._graphics_generation += 1
        self._halfblock_cache = None
        self.refresh(layout=layout)

    def set_graphics_error(self, error: str | None) -> None:
        """Show an error message in place of the frame.

        Args:
            error: Error message, or `None` to clear the error.
        """
        self._graphics_error = error
        self.graphics_changed(layout=True)

    # -- Internals ----------------------------------------------------------

    @property
    def uses_sixel(self) -> bool:
        """Is the widget currently drawn with Sixel?"""
        if self._graphics_error is not None:
            return False
        mode = self.render_mode
        if mode == "auto":
            app = self.app
            return app.graphics_info.sixel and not app.is_inline
        return mode == "sixel"

    @property
    def _graphics_active(self) -> bool:
        """Should the compositor draw this widget's graphics? (Used by the compositor.)"""
        return self.is_mounted and self.uses_sixel and self.get_frame() is not None

    @property
    def _cell_size(self) -> Size:
        return self.app.graphics_info.cell_size

    @property
    def _background_rgb(self) -> tuple[int, int, int]:
        return self.background_colors[1].rgb

    def _graphics_info_changed(self) -> None:
        """Called by the app when the terminal reported its graphics capabilities."""
        self._scaled_cache.clear()
        self._sixel_cache.clear()
        self.graphics_changed(layout=True)

    def watch_fit(self) -> None:
        self.graphics_changed()

    def watch_render_mode(self) -> None:
        self.graphics_changed()

    def _scaled_frame(self, size: tuple[int, int]) -> PILImage | None:
        """Get the frame scaled to a size in pixels."""
        frame = self.get_frame()
        if frame is None:
            return None
        key = (self._graphics_generation, size, self.fit, self._background_rgb)
        scaled = self._scaled_cache.get(key)
        if scaled is None:
            scaled = fit_image(frame, size, self.fit, self._background_rgb)
            self._scaled_cache[key] = scaled
        return scaled

    def _sixel_key(self, content_size: Size, crop: Region) -> tuple:
        return (
            self._graphics_generation,
            content_size,
            crop,
            self._cell_size,
            self.fit,
            self._background_rgb,
            self.sixel_colors,
        )

    def _render_sixel(self, content_size: Size, crop: Region) -> str:
        """Render the visible part of the frame as Sixel. (Used by the compositor.)

        Args:
            content_size: Size of the content region in cells.
            crop: Visible part of the content region, in cells.

        Returns:
            A Sixel sequence.
        """
        from textual._sixel import encode_sixel

        key = self._sixel_key(content_size, crop)
        sixel = self._sixel_cache.get(key)
        if sixel is not None:
            return sixel
        cell_width, cell_height = self._cell_size
        image = self._scaled_frame(
            (content_size.width * cell_width, content_size.height * cell_height)
        )
        if image is None:
            return ""
        if crop.size != content_size:
            image = image.crop(
                (
                    crop.x * cell_width,
                    crop.y * cell_height,
                    crop.right * cell_width,
                    crop.bottom * cell_height,
                )
            )
        sixel = encode_sixel(image, self.sixel_colors)
        self._sixel_cache[key] = sixel
        return sixel

    def _render_error_line(self, y: int, width: int) -> Strip:
        error = self._graphics_error or ""
        lines = [error[offset : offset + width] for offset in range(0, len(error), max(1, width))]
        text = lines[y] if y < len(lines) else ""
        return Strip([Segment(text.ljust(width), self.rich_style)], width)

    def render_line(self, y: int) -> Strip:
        width, height = self.size
        if self._graphics_error is not None:
            return self._render_error_line(y, width)
        background = Style(bgcolor=self.background_colors[1].rich_color)
        if self.uses_sixel and self.get_frame() is not None:
            return graphics_strip(width, background)

        key = (self._graphics_generation, self.size, self.fit, self._background_rgb)
        if self._halfblock_cache is None or self._halfblock_cache[0] != key:
            image = self._scaled_frame((width, height * 2)) if width and height else None
            strips = [] if image is None else halfblock_strips(image)
            self._halfblock_cache = (key, strips)
        strips = self._halfblock_cache[1]
        if y < len(strips):
            return strips[y]
        return Strip.blank(width, background)

    def get_content_width(self, container: Size, viewport: Size) -> int:
        if self._graphics_error is not None:
            return min(container.width, max(1, len(self._graphics_error)))
        size = self.get_frame_size()
        if size is None:
            return 0
        return max(1, min(container.width, ceil(size[0] / self._cell_size.width)))

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        if self._graphics_error is not None:
            return max(1, ceil(len(self._graphics_error) / max(1, width)))
        size = self.get_frame_size()
        if size is None or not width or not size[0]:
            return 0
        cell_width, cell_height = self._cell_size
        return max(1, round(size[1] * (width * cell_width / size[0]) / cell_height))
