"""Fast Sixel encoder (Pillow + NumPy).

The image is quantized with Pillow (implemented in C). Sixel bands and run
detection are computed with NumPy, so the only Python-level loop is over the
long runs and the (band, color) rows that are actually present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

DCS = "\x1bP"
ST = "\x1b\\"

_MIN_RUN = 4
"""Runs shorter than this are written literally (`!3x` is no shorter than `xxx`)."""


def encode_sixel(image: PILImage, colors: int = 256, fast: bool = False) -> str:
    """Encode a Pillow image as a Sixel sequence.

    Every pixel is painted, so the result is opaque. The sequence uses P2=1 so
    that the unused rows of the final (partial) band leave the screen untouched.

    Args:
        image: Image at its final size in pixels.
        colors: Maximum number of colors in the palette (2-256).
        fast: Use a faster palette with lower quality (good for video).

    Returns:
        A complete DCS ... ST sixel sequence (empty string for an empty image).
    """
    import numpy as np
    from PIL import Image

    width, height = image.size
    if not width or not height:
        return ""
    if image.mode != "RGB":
        image = image.convert("RGB")
    colors = max(2, min(256, colors))
    if fast:
        quantized = image.quantize(
            colors=colors,
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.NONE,
        )
    else:
        # Median cut gives a better palette, but is slow; compute it on a
        # downscaled copy and map the full image on to it.
        sample = image
        if width * height > 160_000:
            sample = image.resize(
                (max(1, width // 4), max(1, height // 4)), Image.Resampling.BOX
            )
        palette_image = sample.quantize(
            colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
        )
        quantized = image.quantize(palette=palette_image, dither=Image.Dither.NONE)
    indices = np.asarray(quantized, dtype=np.intp)
    palette_count = int(indices.max()) + 1
    palette = (quantized.getpalette() or [])[: palette_count * 3]

    registers = "".join(
        f"#{index};2;{(r * 100 + 127) // 255};{(g * 100 + 127) // 255};{(b * 100 + 127) // 255}"
        for index, (r, g, b) in enumerate(zip(*[iter(palette)] * 3))
    )
    header = f'{DCS}0;1;0q"1;1;{width};{height}{registers}'

    # Pad to a whole number of bands with a sentinel index that matches no color.
    band_count = (height + 5) // 6
    padded = np.full((band_count * 6, width), palette_count, dtype=np.intp)
    padded[:height] = indices
    bands = padded.reshape(band_count, 6, width)

    # One output row per (band, color) pair present in the image.
    stride = palette_count + 1
    pairs = np.arange(band_count, dtype=np.intp)[:, None, None] * stride + bands
    counts = np.bincount(pairs.ravel(), minlength=band_count * stride)
    counts[palette_count::stride] = 0  # The padding sentinel isn't a color
    present = np.flatnonzero(counts)
    row_count = present.size
    present_band = present // stride
    present_color = present % stride
    row_of_pair = np.full(band_count * stride, row_count, dtype=np.intp)
    row_of_pair[present] = np.arange(row_count, dtype=np.intp)

    # rows[row, x] = sixel value (0..63) of the row's color at column x.
    # Within a single pixel row every (band, x) has exactly one color, so plain
    # fancy-index addition has no duplicate targets. Padding goes to a spare row.
    rows = np.zeros((row_count + 1, width), dtype=np.uint8)
    column_index = np.arange(width, dtype=np.intp)[None, :]
    for bit in range(6):
        rows[row_of_pair[pairs[:, bit, :]], column_index] += 1 << bit
    rows = rows[:row_count]
    rows += 63

    # Run detection over all rows at once.
    flat = rows.ravel()
    total = flat.size
    change = np.empty(total, dtype=bool)
    change[0] = True
    np.not_equal(flat[1:], flat[:-1], out=change[1:])
    change[::width] = True
    starts = np.flatnonzero(change)
    lengths = np.diff(np.append(starts, total))
    ends = starts + lengths
    trailing_blank = (ends % width == 0) & (flat[starts] == 63)
    special = np.flatnonzero((lengths >= _MIN_RUN) | trailing_blank)

    run_values = flat[starts]
    is_long = (lengths >= _MIN_RUN) & ~trailing_blank
    run_repeat = np.where(trailing_blank, 0, np.where(is_long, 1, lengths))

    # Every output "piece" is: [lead byte] [decimal number] [char * repeat].
    # Pieces are row prefixes ("#color"), runs, and row terminators ("$" or "-",
    # the latter after the last color of a band). Sort keys interleave them.
    row_starts = np.arange(row_count, dtype=np.int64) * width
    last_in_band = np.ones(row_count, dtype=bool)
    last_in_band[:-1] = present_band[1:] != present_band[:-1]
    run_count = starts.size

    keys = np.concatenate(
        (row_starts * 3, starts.astype(np.int64) * 3 + 1, (row_starts + width) * 3 - 1)
    )
    lead = np.concatenate(
        (
            np.full(row_count, ord("#"), np.uint8),
            np.where(is_long, ord("!"), 0).astype(np.uint8),
            np.zeros(row_count, np.uint8),
        )
    )
    number = np.concatenate(
        (present_color, np.where(is_long, lengths, -1), np.full(row_count, -1))
    ).astype(np.int64)
    char = np.concatenate(
        (
            np.zeros(row_count, np.uint8),
            run_values,
            np.where(last_in_band, ord("-"), ord("$")).astype(np.uint8),
        )
    )
    repeat = np.concatenate(
        (np.zeros(row_count, np.int64), run_repeat, np.ones(row_count, np.int64))
    )
    order = np.argsort(keys, kind="stable")
    lead, number, char, repeat = lead[order], number[order], char[order], repeat[order]

    has_lead = (lead != 0).astype(np.int64)
    digits = np.zeros(number.size, np.int64)
    has_number = number >= 0
    digits[has_number] = np.floor(np.log10(np.maximum(number[has_number], 1))).astype(np.int64) + 1
    piece_size = has_lead + digits + repeat
    offsets = np.zeros(piece_size.size, np.int64)
    np.cumsum(piece_size[:-1], out=offsets[1:])
    out = np.empty(int(offsets[-1] + piece_size[-1]), np.uint8)

    lead_mask = has_lead.astype(bool)
    out[offsets[lead_mask]] = lead[lead_mask]
    max_digits = int(digits.max()) if digits.size else 0
    for place in range(max_digits):
        mask = digits > place
        power = 10 ** (digits[mask] - 1 - place)
        out[offsets[mask] + has_lead[mask] + place] = (number[mask] // power) % 10 + 48

    char_start = offsets + has_lead + digits
    char_mask = repeat > 0
    run_starts_out = char_start[char_mask]
    run_repeats = repeat[char_mask]
    run_total = int(run_repeats.sum())
    within = np.arange(run_total, dtype=np.int64) - np.repeat(
        np.cumsum(run_repeats) - run_repeats, run_repeats
    )
    out[np.repeat(run_starts_out, run_repeats) + within] = np.repeat(
        char[char_mask], run_repeats
    )
    del run_count

    return header + out.tobytes().decode("ascii") + ST
