"""Shared drawing helpers for a head-swap template.

Copy this file next to the template's ``__init__.py``.  It only depends on
Pillow, pil_utils, and meme-generator 0.1.x, so the template directory can be
copied into any external meme repo without extra runtime dependencies.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter
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


def _face_crop(image: Image.Image, ratio: float) -> Image.Image:
    """Crop a square around the busiest part of the avatar (eyes, mouth, edges).

    The edge-energy centroid is blended half-way with the image center so a
    busy background cannot drag the crop off the face.  ``ratio`` < 1 removes
    the avatar's border (hat brim, shoulders, background) without cutting the
    chin: 0.85 keeps a normal headshot intact and still trims the frame.
    """

    width, height = image.size
    side = max(1, int(min(width, height) * ratio))
    small = image.convert("L").resize((64, 64), Image.BILINEAR)
    data = list(small.filter(ImageFilter.FIND_EDGES).getdata())

    total = 0.0
    sum_x = 0.0
    sum_y = 0.0
    for y in range(64):
        row = y * 64
        for x in range(64):
            value = data[row + x]
            if value < 24:
                continue
            total += value
            sum_x += x * value
            sum_y += y * value

    if total:
        cx = (sum_x / total) / 64 * width
        cy = (sum_y / total) / 64 * height
        cx = cx * 0.5 + width * 0.25
        cy = cy * 0.5 + height * 0.25
    else:
        cx, cy = width / 2, height / 2

    left = min(max(0, round(cx - side / 2)), width - side)
    top = min(max(0, round(cy - side / 2)), height - side)
    return image.crop((left, top, left + side, top + side))


def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
    """Scale-and-crop (no stretching) so the image fills width x height."""

    scale = max(width / image.width, height / image.height)
    new_width = max(width, round(image.width * scale))
    new_height = max(height, round(image.height * scale))
    resized = image.resize((new_width, new_height), Image.LANCZOS)
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def avatar(
    images,
    width: int,
    height: int | None = None,
    *,
    shape: str = "circle",
    zoom: float = 0.85,
) -> Image.Image:
    """Crop the input avatar to the face and mask it to a circle/ellipse/rect.

    The layer has no outline: the original meme already draws its own face
    edge, and an added ring reads as a pasted sticker.
    """

    height = width if height is None else height
    raw = images[0].convert("RGBA").image
    image = _cover(_face_crop(raw, zoom), width, height)
    if shape == "rect":
        return image

    oversample = 4
    mask = Image.new("L", (width * oversample, height * oversample), 0)
    ImageDraw.Draw(mask).ellipse(
        (0, 0, width * oversample - 1, height * oversample - 1), fill=255
    )
    mask = mask.resize((width, height), Image.LANCZOS)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    layer.paste(image, (0, 0), mask)
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
