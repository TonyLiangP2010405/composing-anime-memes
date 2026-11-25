"""Shared drawing helpers for a head-swap template.

Copy this file next to the template's ``__init__.py``.  It only depends on
Pillow, pil_utils, and meme-generator 0.1.x, so the template directory can be
copied into any external meme repo without extra runtime dependencies.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw
from pil_utils import Text2Image

from meme_generator.utils import save_gif

FONT_FAMILIES = [
    "Noto Sans SC",
    "PingFang SC",
    "Microsoft YaHei",
    "Source Han Sans SC",
    "WenQuanYi Micro Hei",
    "Arial Unicode MS",
]

INK = (24, 24, 24, 255)


def load_frames(path) -> list[Image.Image]:
    """Load every frame of a GIF/PNG as RGBA."""

    frames: list[Image.Image] = []
    with Image.open(path) as image:
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            frames.append(image.convert("RGBA"))
    return frames


def avatar(
    images,
    width: int,
    height: int | None = None,
    *,
    shape: str = "circle",
) -> Image.Image:
    """Crop the input avatar to a circle/ellipse/rect with a thin outline.

    ``shape="circle"`` uses ``width`` for both axes.  ``shape="ellipse"``
    accepts a different ``height`` and is the way to cover a face while leaving
    panda ears visible.
    """

    height = width if height is None else height
    image = images[0].convert("RGBA").square().resize((width, height))
    if shape == "rect":
        layer = image.image
        ImageDraw.Draw(layer).rectangle((0, 0, width - 1, height - 1), outline=INK, width=3)
        return layer

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, width - 1, height - 1), fill=255)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    layer.paste(image.image, (0, 0), mask)
    ImageDraw.Draw(layer).ellipse((0, 0, width - 1, height - 1), outline=INK, width=3)
    return layer


def paste_center(frame: Image.Image, layer: Image.Image, center: tuple[int, int]) -> None:
    """Paste a layer centered at ``center``; clip if it exceeds the frame."""

    x = int(center[0] - layer.width / 2)
    y = int(center[1] - layer.height / 2)
    left = max(0, -x)
    top = max(0, -y)
    right = min(layer.width, frame.width - x)
    bottom = min(layer.height, frame.height - y)
    if right <= left or bottom <= top:
        return
    if (left, top, right, bottom) != (0, 0, layer.width, layer.height):
        layer = layer.crop((left, top, right, bottom))
        x += left
        y += top
    frame.alpha_composite(layer, (x, y))


def text_img(
    text: str,
    size: int,
    *,
    fill=(255, 255, 255, 255),
    stroke_width: int = 4,
    stroke_fill=(0, 0, 0, 255),
) -> Image.Image:
    return Text2Image.from_text(
        text,
        size,
        font_families=FONT_FAMILIES,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    ).to_image().convert("RGBA")


def animate_static(
    frame: Image.Image,
    count: int,
    *,
    zoom: float = 1.05,
    zoom_amp: float = 0.0,
    shake: int = 3,
) -> list[Image.Image]:
    """Add a slight push/pull or shake to a static meme so it still animates."""

    frames: list[Image.Image] = []
    width, height = frame.size
    for index in range(count):
        t = index / max(1, count - 1)
        scale = zoom + zoom_amp * math.sin(t * math.pi * 2)
        big = frame.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
        dx = (big.width - width) // 2 + int(shake * math.sin(index * 1.7))
        dy = (big.height - height) // 2 + int(shake * math.cos(index * 2.1))
        frames.append(big.crop((dx, dy, dx + width, dy + height)))
    return frames


def save(frames, duration: float):
    return save_gif([frame.convert("RGB") for frame in frames], duration)
