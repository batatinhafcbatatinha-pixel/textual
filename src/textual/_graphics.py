"""Support for terminal graphics (Sixel) and its half-block fallback.

Graphics widgets mark the cells covered by an image with `GRAPHICS_CHAR`. When a
strip is rendered to terminal sequences those cells become cursor movements
(`CSI n C`) instead of text, so the compositor never overwrites (and erases) the
image. The compositor emits the image itself (see `Compositor._update_graphics`)
before the text of the same frame, inside a synchronized update.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from rich.segment import Segment
from rich.style import Style

from textual.geometry import Size

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

    from textual.strip import Strip

GRAPHICS_CHAR = "\U0010fffd"
"""Placeholder character for a cell covered by a graphic (a private use character with cell width 1)."""

_RE_GRAPHICS_RUN = re.compile(f"{GRAPHICS_CHAR}+")

RenderMode = Literal["auto", "sixel", "halfblock"]
Fit = Literal["contain", "cover", "fill"]

DEFAULT_CELL_SIZE = Size(10, 20)


@dataclass(frozen=True)
class GraphicsInfo:
    """Graphics capabilities of the terminal."""

    sixel: bool = False
    """Does the terminal support Sixel?"""
    cell_size: Size = field(default=DEFAULT_CELL_SIZE)
    """Size of a cell in pixels."""

    @classmethod
    def from_environment(cls) -> GraphicsInfo:
        """Initial graphics info, which may be forced with `TEXTUAL_GRAPHICS=sixel`."""
        return cls(sixel=os.environ.get("TEXTUAL_GRAPHICS", "").lower() == "sixel")


def forced_render_mode() -> RenderMode | None:
    """Get a render mode forced by the `TEXTUAL_GRAPHICS` environment variable."""
    mode = os.environ.get("TEXTUAL_GRAPHICS", "").lower()
    if mode in ("sixel", "halfblock"):
        return mode  # type: ignore[return-value]
    return None


def render_graphics_text(text: str, style: Style | None, render_style) -> str:
    """Render text which contains graphics placeholders.

    Placeholder runs are replaced with cursor forward movements, other text is
    rendered normally.

    Args:
        text: Segment text.
        style: Segment style.
        render_style: Callable to render styled text.

    Returns:
        Terminal sequences.
    """
    output: list[str] = []
    append = output.append
    position = 0
    for match in _RE_GRAPHICS_RUN.finditer(text):
        start, end = match.span()
        if start > position:
            plain = text[position:start]
            append(plain if style is None else render_style(style, plain))
        append(f"\x1b[{end - start}C")
        position = end
    if position < len(text):
        plain = text[position:]
        append(plain if style is None else render_style(style, plain))
    return "".join(output)


def graphics_strip(width: int, style: Style | None = None) -> Strip:
    """A strip of placeholder cells.

    Args:
        width: Width in cells.
        style: Style (used if the strip is ever rendered as text, e.g. in a screenshot).

    Returns:
        A Strip.
    """
    from textual.strip import Strip

    return Strip([Segment(GRAPHICS_CHAR * width, style)], width)


def fit_image(
    image: PILImage,
    size: tuple[int, int],
    fit: Fit,
    background: tuple[int, int, int],
) -> PILImage:
    """Scale an image to a target size in pixels.

    Args:
        image: Source image (any mode; transparency is flattened on `background`).
        size: Target size (width, height) in pixels.
        fit: "contain" keeps the aspect ratio and letterboxes with `background`,
            "cover" keeps the aspect ratio and crops, "fill" stretches.
        background: Background color for letterboxing and transparency.

    Returns:
        An RGB image of exactly `size`.
    """
    from PIL import Image

    target_width, target_height = size
    width, height = image.size
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert(
            "RGBA" if ("A" in image.mode or "transparency" in image.info) else "RGB"
        )
    if image.mode == "RGBA":
        flattened = Image.new("RGB", image.size, background)
        flattened.paste(image, mask=image.getchannel("A"))
        image = flattened

    if not width or not height or not target_width or not target_height:
        return Image.new("RGB", (max(1, target_width), max(1, target_height)), background)

    resample = Image.Resampling.BILINEAR
    if fit == "fill":
        return image.resize((target_width, target_height), resample)

    if fit == "cover":
        scale = max(target_width / width, target_height / height)
        scaled_width = max(1, round(width * scale))
        scaled_height = max(1, round(height * scale))
        left = (scaled_width - target_width) // 2
        top = (scaled_height - target_height) // 2
        box = (
            left / scale,
            top / scale,
            (left + target_width) / scale,
            (top + target_height) / scale,
        )
        return image.resize((target_width, target_height), resample, box=box)

    scale = min(target_width / width, target_height / height)
    scaled_width = max(1, min(target_width, round(width * scale)))
    scaled_height = max(1, min(target_height, round(height * scale)))
    if (scaled_width, scaled_height) == (target_width, target_height):
        return image.resize((target_width, target_height), resample)
    canvas = Image.new("RGB", (target_width, target_height), background)
    canvas.paste(
        image.resize((scaled_width, scaled_height), resample),
        ((target_width - scaled_width) // 2, (target_height - scaled_height) // 2),
    )
    return canvas


def contain_size(
    source: tuple[int, int], target: tuple[int, int]
) -> tuple[int, int]:
    """Size of `source` scaled to fit within `target`, keeping the aspect ratio."""
    width, height = source
    target_width, target_height = target
    if not width or not height:
        return (0, 0)
    scale = min(target_width / width, target_height / height)
    return (
        max(1, min(target_width, round(width * scale))),
        max(1, min(target_height, round(height * scale))),
    )


def halfblock_strips(image: PILImage) -> list[Strip]:
    """Render an RGB image as strips of upper half blocks.

    Each cell shows two vertical pixels: the foreground color is the top pixel,
    the background color the bottom pixel.

    Args:
        image: RGB image whose height is twice the number of lines.

    Returns:
        One strip per line.
    """
    import numpy as np
    from rich.color import Color as RichColor

    from textual.strip import Strip

    pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width = pixels.shape[:2]
    if height % 2:
        pixels = np.concatenate((pixels, pixels[-1:]), axis=0)
    top = pixels[0::2]
    bottom = pixels[1::2]
    styles: dict[tuple, Style] = {}
    from_rgb = RichColor.from_rgb
    strips: list[Strip] = []
    for top_row, bottom_row in zip(top.tolist(), bottom.tolist()):
        segments: list[Segment] = []
        append = segments.append
        previous = None
        run = 0
        for top_pixel, bottom_pixel in zip(top_row, bottom_row):
            key = (*top_pixel, *bottom_pixel)
            if key == previous:
                run += 1
                continue
            if previous is not None:
                append(Segment("▀" * run, styles[previous]))
            if key not in styles:
                styles[key] = Style(color=from_rgb(*top_pixel), bgcolor=from_rgb(*bottom_pixel))
            previous = key
            run = 1
        if previous is not None:
            append(Segment("▀" * run, styles[previous]))
        strips.append(Strip(segments, width))
    return strips
