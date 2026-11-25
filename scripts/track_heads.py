"""Track a face across an animated meme and emit per-frame head centers.

The template stores one center per frame so the replacement avatar follows the
original head instead of staying pinned to one coordinate.  Optical flow on the
face's own features (eyes, nose, mouth, edges) is more stable than template
matching the whole face: panda faces change expression and color between frames,
and whole-face matching tends to jump to an ear or the body.

Usage:
    python scripts/track_heads.py --file base.gif --box 80,22,100,100 --out /tmp/track

Requires: opencv-python-headless, numpy, Pillow.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x,y,w,h")
    return tuple(parts)  # type: ignore[return-value]


def load_gray(path: Path) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    with Image.open(path) as image:
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            frames.append(
                cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
            )
    return frames


def track(frames: list[np.ndarray], box: tuple[int, int, int, int], search: int) -> list[tuple[float, float]]:
    x, y, width, height = box
    mask = np.zeros_like(frames[0])
    mask[y : y + height, x : x + width] = 255
    points = cv2.goodFeaturesToTrack(
        frames[0],
        maxCorners=80,
        qualityLevel=0.01,
        minDistance=4,
        mask=mask,
    )
    center = [x + width / 2.0, y + height / 2.0]
    centers: list[tuple[float, float]] = [(center[0], center[1])]

    for index in range(1, len(frames)):
        if points is None or len(points) < 4:
            centers.append((center[0], center[1]))
            continue
        next_points, status, _error = cv2.calcOpticalFlowPyrLK(
            frames[index - 1], frames[index], points, None
        )
        good = status.reshape(-1) == 1
        if good.sum() < 4:
            centers.append((center[0], center[1]))
            points = next_points[good].reshape(-1, 1, 2) if good.any() else None
            continue
        delta = (next_points.reshape(-1, 2) - points.reshape(-1, 2))[good]
        dx = float(np.median(delta[:, 0]))
        dy = float(np.median(delta[:, 1]))
        dx = max(-search, min(search, dx))
        dy = max(-search, min(search, dy))
        center[0] += dx
        center[1] += dy
        centers.append((center[0], center[1]))
        points = next_points[good].reshape(-1, 1, 2)

    return centers


def render_sheet(frames: list[np.ndarray], centers: list[tuple[float, float]], out: Path) -> None:
    cell_w, cell_h, pad, label_h = 220, 220, 8, 26
    cols = min(6, len(frames))
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new(
        "RGB",
        (cell_w * cols + pad * (cols + 1), (cell_h + label_h) * rows + pad * (rows + 1)),
        (240, 240, 242),
    )
    draw = ImageDraw.Draw(sheet)
    for index, gray in enumerate(frames):
        original_h, original_w = gray.shape[:2]
        frame = Image.fromarray(gray).convert("RGB")
        frame.thumbnail((cell_w, cell_h))
        scale_x = frame.width / original_w
        scale_y = frame.height / original_h
        col, row = index % cols, index // cols
        x = pad + col * (cell_w + pad)
        y = pad + row * (cell_h + label_h + pad)
        sheet.paste(frame, (x + (cell_w - frame.width) // 2, y + (cell_h - frame.height) // 2))
        cx, cy = centers[index]
        px = x + (cell_w - frame.width) // 2 + cx * scale_x
        py = y + (cell_h - frame.height) // 2 + cy * scale_y
        draw.line((px - 10, py, px + 10, py), fill=(255, 0, 0), width=2)
        draw.line((px, py - 10, px, py + 10), fill=(255, 0, 0), width=2)
        draw.text((x + 2, y + cell_h + 3), f"#{index} ({cx:.0f},{cy:.0f})", fill=(20, 20, 20))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--box", required=True, type=parse_box, help="initial face box x,y,w,h")
    parser.add_argument("--search", type=int, default=60, help="max per-frame displacement")
    parser.add_argument("--out", type=Path, default=Path("/tmp/track_heads.png"))
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    frames = load_gray(args.file)
    centers = track(frames, args.box, args.search)

    rounded = [(round(cx, 1), round(cy, 1)) for cx, cy in centers]
    print("HEAD_CENTERS = [")
    for index in range(0, len(rounded), 4):
        chunk = ", ".join(f"({cx:g}, {cy:g})" for cx, cy in rounded[index : index + 4])
        print(f"    {chunk},")
    print("]")

    render_sheet(frames, centers, args.out)
    print(f"visualization: {args.out}")

    if args.json is not None:
        args.json.write_text(
            json.dumps({"centers": rounded}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"json: {args.json}")


if __name__ == "__main__":
    main()
