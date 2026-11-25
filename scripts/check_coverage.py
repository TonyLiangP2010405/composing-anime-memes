"""Check whether the replacement avatar fully covers the face box.

A circle whose diameter equals the face width leaves the four corners of the
face exposed (cheeks, chin, forehead).  The minimum diameter is the face box
diagonal, sqrt(w^2 + h^2), plus a 3-5 px margin for tracking jitter.

An ellipse mask is for preserving panda ears.  It cannot cover the rectangle's
four corners without growing to sqrt(2) x the box (which would cover the ears
too), so ellipse mode checks the inner 70% face rectangle and prints
COVERED (ELLIPSE); visual review must confirm no old facial feature is left.

It can read the template's meta.json directly:

    python scripts/check_coverage.py --meta /path/to/template/meta.json --frame 0

or take explicit values:

    python scripts/check_coverage.py --file base.gif --box 80,22,100,110 --size 156 --center 130,77
    python scripts/check_coverage.py --file base.gif --box 80,22,100,110 --shape ellipse --ellipse 150x160 --center 130,77
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ELLIPSE_INNER = 0.7


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x,y,w,h")
    return tuple(parts)  # type: ignore[return-value]


def parse_point(value: str) -> tuple[int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("point must be x,y")
    return tuple(parts)  # type: ignore[return-value]


def parse_ellipse(value: str) -> tuple[int, int]:
    parts = [int(part.strip()) for part in value.lower().replace("x", ",").split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("ellipse must be WxH")
    return tuple(parts)  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta", type=Path, default=None, help="template meta.json")
    parser.add_argument("--file", type=Path, default=None)
    parser.add_argument("--box", type=parse_box, default=None, help="face box x,y,w,h")
    parser.add_argument("--size", type=int, default=0, help="avatar circle diameter")
    parser.add_argument("--center", type=parse_point, default=None, help="avatar center x,y")
    parser.add_argument("--shape", choices=("circle", "ellipse"), default=None)
    parser.add_argument("--ellipse", type=parse_ellipse, default=None, help="ellipse WxH")
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--out", type=Path, default=Path("/tmp/coverage.png"))
    args = parser.parse_args()

    explicit_box = args.box is not None
    explicit_center = args.center is not None
    if explicit_box != explicit_center:
        parser.error("when overriding meta, pass both --box and --center")

    meta = None
    if args.meta is not None:
        meta = json.loads(args.meta.read_text(encoding="utf-8"))
        if args.file is None:
            args.file = args.meta.parent / str(meta["source"])
        if args.box is None:
            args.box = tuple(int(value) for value in meta["face_box"])
        if args.size <= 0:
            args.size = int(meta.get("avatar_size") or 0)
        if args.ellipse is None and meta.get("ellipse_size"):
            args.ellipse = tuple(int(value) for value in meta["ellipse_size"])

    if args.file is None or args.box is None:
        parser.error("provide --meta or both --file and --box")

    with Image.open(args.file) as image:
        frame_count = getattr(image, "n_frames", 1)
        if not 0 <= args.frame < frame_count:
            parser.error(f"--frame must be 0..{frame_count - 1}")
        image.seek(args.frame)
        frame = image.convert("RGB")

    shape = args.shape or (meta or {}).get("shape", "circle")
    if shape == "circle" and args.size <= 0:
        parser.error("--size is required for circle")
    if shape == "ellipse" and args.ellipse is None:
        parser.error("--ellipse WxH is required for ellipse")

    x, y, width, height = args.box
    if meta is not None:
        centers = meta.get("centers") or []
        if centers and len(centers) not in (1, frame_count):
            parser.error(
                f"meta has {len(centers)} centers but source has {frame_count} frames"
            )
        if centers:
            base = centers[0]
            current = centers[args.frame] if len(centers) > 1 else centers[0]
            if not explicit_center:
                args.center = tuple(int(value) for value in current)
            if not explicit_box and (
                int(current[0]) != int(base[0]) or int(current[1]) != int(base[1])
            ):
                args.box = (
                    x + int(current[0]) - int(base[0]),
                    y + int(current[1]) - int(base[1]),
                    width,
                    height,
                )

    x, y, width, height = args.box
    cx = args.center[0] if args.center else x + width / 2
    cy = args.center[1] if args.center else y + height / 2
    corners = [(x, y), (x + width, y), (x, y + height), (x + width, y + height)]

    if shape == "circle":
        diameter = args.size
        radius = diameter / 2
        distances = [math.hypot(px - cx, py - cy) for px, py in corners]
        covered = all(distance <= radius for distance in distances)
        required = math.hypot(width, height)
        shape_box = (cx - radius, cy - radius, cx + radius, cy + radius)
        print(f"face box: {args.box}")
        print(f"avatar circle: center=({cx:g},{cy:g}) diameter={diameter}")
        print(f"required minimum diameter: {required:.1f}")
        print(f"recommended diameter (D_min + 5): {required + 5:.0f}")
        print(f"max corner distance: {max(distances):.1f}")
    else:
        ellipse_w, ellipse_h = args.ellipse
        half_w, half_h = ellipse_w / 2, ellipse_h / 2
        inner_w, inner_h = width * ELLIPSE_INNER, height * ELLIPSE_INNER
        inner_corners = [
            (cx - inner_w / 2, cy - inner_h / 2),
            (cx + inner_w / 2, cy - inner_h / 2),
            (cx - inner_w / 2, cy + inner_h / 2),
            (cx + inner_w / 2, cy + inner_h / 2),
        ]
        values = [
            ((px - cx) / half_w) ** 2 + ((py - cy) / half_h) ** 2
            for px, py in inner_corners
        ]
        covered = all(value <= 1.0 for value in values)
        shape_box = (cx - half_w, cy - half_h, cx + half_w, cy + half_h)
        print(f"face box: {args.box}")
        print(f"avatar ellipse: center=({cx:g},{cy:g}) size={ellipse_w}x{ellipse_h}")
        print(
            f"inner {ELLIPSE_INNER:.0%} face rectangle: "
            f"{inner_w:.1f}x{inner_h:.1f}, max normalized value {max(values):.3f}"
        )
        print("note: ellipse corners are ears/background; visual review required")

    draw = ImageDraw.Draw(frame)
    draw.rectangle((x, y, x + width, y + height), outline=(0, 200, 0), width=3)
    draw.ellipse(shape_box, outline=(255, 0, 0), width=3)
    draw.line((cx - 8, cy, cx + 8, cy), fill=(255, 0, 0), width=2)
    draw.line((cx, cy - 8, cx, cy + 8), fill=(255, 0, 0), width=2)
    if shape == "ellipse":
        inner_box = (
            cx - width * ELLIPSE_INNER / 2,
            cy - height * ELLIPSE_INNER / 2,
            cx + width * ELLIPSE_INNER / 2,
            cy + height * ELLIPSE_INNER / 2,
        )
        draw.rectangle(inner_box, outline=(0, 120, 255), width=2)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.save(args.out)
    print(f"diagnostic: {args.out}")
    if covered:
        print("COVERED (ELLIPSE)" if shape == "ellipse" else "COVERED")
    else:
        print("NOT COVERED")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
