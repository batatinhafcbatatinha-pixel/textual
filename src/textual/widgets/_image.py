"""A widget to display an image (Sixel, or half blocks when Sixel isn't available)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Union

from textual._graphics import Fit, RenderMode
from textual._graphics_widget import MEDIA_INSTALL_HINT, GraphicsWidget

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage
    from typing_extensions import TypeAlias

ImageSource: TypeAlias = Union[str, Path, bytes, "PILImage", None]
"""A path, encoded image data, a Pillow image, or `None` for no image."""


def load_image(source: ImageSource) -> PILImage | None:
    """Load an image.

    Args:
        source: A path, encoded image data, or a Pillow image.

    Returns:
        A Pillow image (fully loaded, with EXIF orientation applied).
    """
    from PIL import Image as PILImageModule
    from PIL import ImageOps

    if source is None:
        return None
    if isinstance(source, PILImageModule.Image):
        return source
    if isinstance(source, bytes):
        image = PILImageModule.open(BytesIO(source))
    else:
        image = PILImageModule.open(Path(source).expanduser())
    image.load()
    return ImageOps.exif_transpose(image) or image


class Image(GraphicsWidget):
    """Displays an image.

    Uses Sixel when the terminal supports it, and colored half blocks otherwise.
    With `width: auto` and/or `height: auto` (the default) the widget takes the
    natural size of the image (limited to the width of its container).

    Requires Pillow and NumPy (`pip install textual[media]`).
    """

    DEFAULT_CSS = """
    Image {
        width: auto;
        height: auto;
    }
    """

    def __init__(
        self,
        image: ImageSource = None,
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
            image: A path, encoded image data, a Pillow image, or `None`.
            fit: How the image is scaled: "contain" (keep aspect ratio, fill the
                rest with the background color), "cover" (keep aspect ratio, crop),
                or "fill" (stretch).
            render_mode: "auto" (Sixel if supported), "sixel", or "halfblock".
            colors: Maximum number of colors in the Sixel palette (2-256).
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: The CSS classes of the widget.
            disabled: Whether the widget is disabled or not.
        """
        super().__init__(
            fit=fit,
            render_mode=render_mode,
            colors=colors,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self._image: PILImage | None = None
        self.image = image

    @property
    def image(self) -> PILImage | None:
        """The Pillow image displayed (set a path, bytes, or Pillow image to change it)."""
        return self._image

    @image.setter
    def image(self, source: ImageSource) -> None:
        try:
            self._image = load_image(source)
        except ImportError:
            self._image = None
            self.set_graphics_error(f"Image requires Pillow: {MEDIA_INSTALL_HINT}")
            return
        except Exception as error:
            self._image = None
            self.set_graphics_error(f"Unable to load image: {error}")
            return
        self._graphics_error = None
        self.graphics_changed(layout=True)

    def get_frame(self) -> PILImage | None:
        return self._image
