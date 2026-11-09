from __future__ import annotations

import re

import numpy as np
import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image

from textual._sixel import encode_sixel


def decode_sixel(sequence: str) -> np.ndarray:
    """Minimal Sixel decoder for tests: returns an (h, w, 3) array of 0-100 percentages (-1 = unset)."""
    match = re.match(r'\x1bP[\d;]*q"1;1;(\d+);(\d+)(.*)\x1b\\\Z', sequence, re.S)
    assert match, sequence[:40]
    width, height, body = int(match[1]), int(match[2]), match[3]
    out = np.full((height, width, 3), -1, dtype=np.int16)
    palette: dict[int, tuple[int, int, int]] = {}
    color = 0
    x = 0
    band = 0
    for token in re.finditer(r"#(\d+);2;(\d+);(\d+);(\d+)|#(\d+)|!(\d+)(.)|([?-~])|\$|-", body):
        text = token.group()
        if token[1] is not None:
            palette[int(token[1])] = (int(token[2]), int(token[3]), int(token[4]))
            continue
        if token[5] is not None:
            color = int(token[5])
            continue
        if text == "$":
            x = 0
            continue
        if text == "-":
            x = 0
            band += 1
            continue
        if token[6] is not None:
            count, char = int(token[6]), token[7]
        else:
            count, char = 1, token[8]
        bits = ord(char) - 63
        for _ in range(count):
            for bit in range(6):
                y = band * 6 + bit
                if bits & (1 << bit) and y < height:
                    out[y, x] = palette[color]
            x += 1
    return out


def to_percent(array: np.ndarray) -> np.ndarray:
    return (array.astype(np.int32) * 100 + 127) // 255


@pytest.mark.parametrize("size", [(1, 1), (5, 7), (12, 6), (37, 23), (80, 40)])
def test_round_trip_exact_with_few_colors(size):
    rng = np.random.default_rng(1)
    palette = rng.integers(0, 256, (6, 3), dtype=np.uint8)
    indices = rng.integers(0, 6, (size[1], size[0]))
    # Long runs too
    indices[:, : size[0] // 2] = 2
    pixels = palette[indices]
    image = Image.fromarray(pixels, "RGB")
    decoded = decode_sixel(encode_sixel(image))
    assert (decoded >= 0).all(), "every pixel must be painted"
    np.testing.assert_array_equal(decoded, to_percent(pixels))


def test_photo_is_close():
    rng = np.random.default_rng(2)
    small = rng.integers(0, 256, (12, 20, 3), dtype=np.uint8)
    image = Image.fromarray(small, "RGB").resize((200, 120), Image.Resampling.BICUBIC)
    decoded = decode_sixel(encode_sixel(image, colors=256))
    assert (decoded >= 0).all()
    error = np.abs(decoded - to_percent(np.asarray(image))).mean()
    assert error < 6  # mean error in percent (random image: worst case for quantization)


def test_header_and_transparency_mode():
    sequence = encode_sixel(Image.new("RGB", (4, 7), (255, 0, 0)))
    assert sequence.startswith('\x1bP0;1;0q"1;1;4;7#0;2;100;0;0')
    assert sequence.endswith("\x1b\\")


def test_empty():
    assert encode_sixel(Image.new("RGB", (0, 0))) == ""
