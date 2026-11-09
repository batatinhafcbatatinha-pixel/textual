"""Generate a colorful sample image (sample.png) for the media demo."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

width, height = 640, 400
y, x = np.mgrid[0:height, 0:width]
red = (np.sin(x / 60) * 0.5 + 0.5) * 255
green = (np.cos(y / 45) * 0.5 + 0.5) * 255
blue = ((x + y) / (width + height)) * 255
image = Image.fromarray(np.dstack([red, green, blue]).astype(np.uint8), "RGB")
draw = ImageDraw.Draw(image)
draw.ellipse((220, 110, 420, 290), fill=(250, 220, 40), outline=(0, 0, 0), width=6)
draw.rectangle((40, 40, 160, 160), fill=(20, 20, 20))
draw.text((60, 90), "Textual", fill=(255, 255, 255))
image.save(Path(__file__).parent / "sample.png")
