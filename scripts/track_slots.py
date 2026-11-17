"""Track a geometric slot across the frames of an animated meme.

An animated 斗图 moves: a magnifier lens slides over a face, a phone is raised, a screen tilts.
The avatar has to follow that motion, so the template stores one box per frame instead of a
single static box.  This tool matches the artwork *around* the slot (the lens rim, the screen
bezel, the frame border) from the first frame onto every other frame, which gives a per-frame
offset that is far more stable than re-detecting the shape each time.

    python tools/track_slots.py --file meme.gif --shape circle --box 72,63,172,172

Prints a JSON list of per-frame boxes and prints the drift range so the tracking can be checked.
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def load_frames(path):
    frames = []
    with Image.open(path) as image:
        count = getattr(image, "n_frames", 1)
        for index in range(count):
            image.seek(index)
            frames.append(np.asarray(image.convert("RGB")))
    return frames


def ring_mask(shape, patch_size, box_in_patch, band_inner, band_outer):
    """Mask over the artwork that surrounds the slot: lens rim (circle) or bezel (rect)."""
    height, width = patch_size
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    if shape == "circle":
        cx, cy = box_in_patch[0] + box_in_patch[2] / 2.0, box_in_patch[1] + box_in_patch[3] / 2.0
        radius = min(box_in_patch[2], box_in_patch[3]) / 2.0
        distance = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        return ((distance > radius * band_inner) & (distance < radius * band_outer)).astype(np.float32)
    left, top = box_in_patch[0], box_in_patch[1]
    right, bottom = left + box_in_patch[2], top + box_in_patch[3]
    inside = (xx >= left) & (xx <= right) & (yy >= top) & (yy <= bottom)
    return (~inside).astype(np.float32)


def track(frames, shape, box, search_ratio=0.18, band=(0.86, 1.22), min_score=0.86):
    """Return one [x, y, w, h] per frame by matching the slot's border band.

    Tracking is sequential (each frame is matched near the previous position) so a fast moving
    subject cannot make the match jump across the image.  Frames whose correlation is weak or
    whose step is implausibly large are dropped and filled in by interpolation.
    """
    height, width = frames[0].shape[:2]
    x, y, box_width, box_height = box
    pad = int(round(max(box_width, box_height) * 0.28))
    x0 = max(0, int(round(x - pad)))
    y0 = max(0, int(round(y - pad)))
    x1 = min(width, int(round(x + box_width + pad)))
    y1 = min(height, int(round(y + box_height + pad)))
    patch = frames[0][y0:y1, x0:x1]
    gray_patch = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY).astype(np.float32)
    mask = ring_mask(shape, (y1 - y0, x1 - x0), (x - x0, y - y0, box_width, box_height), band[0], band[1])
    mask = cv2.GaussianBlur(mask, (3, 3), 0.8)
    if mask.sum() < 50:
        mask = np.ones_like(mask)
    search = max(4, int(round(max(box_width, box_height) * search_ratio)))
    max_step = max(box_width, box_height) * search_ratio * 1.6
    positions = []
    previous = (x, y)
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY).astype(np.float32)
        sx0 = max(0, int(round(previous[0])) - pad - search)
        sy0 = max(0, int(round(previous[1])) - pad - search)
        sx1 = min(width, int(round(previous[0])) + int(round(box_width)) + pad + search)
        sy1 = min(height, int(round(previous[1])) + int(round(box_height)) + pad + search)
        window = gray[sy0:sy1, sx0:sx1]
        if window.shape[0] < patch.shape[0] or window.shape[1] < patch.shape[1]:
            positions.append((previous, 0.0))
            continue
        result = cv2.matchTemplate(window, gray_patch, cv2.TM_CCORR_NORMED, mask=mask)
        _, score, _, max_location = cv2.minMaxLoc(result)
        candidate = (sx0 + max_location[0] + (x - x0), sy0 + max_location[1] + (y - y0))
        step = abs(candidate[0] - previous[0]) + abs(candidate[1] - previous[1])
        if score < min_score or step > max_step:
            positions.append((previous, score))
            continue
        positions.append((candidate, score))
        previous = candidate
    good = [index for index, (_, score) in enumerate(positions) if score >= min_score]
    boxes = []
    for index, (position, score) in enumerate(positions):
        if score >= min_score:
            boxes.append([round(float(position[0]), 1), round(float(position[1]), 1), round(box_width, 1), round(box_height, 1)])
            continue
        before = [value for value in good if value < index]
        after = [value for value in good if value > index]
        if before and after:
            left, right = before[-1], after[0]
            ratio = (index - left) / float(right - left)
            xa, ya = positions[left][0]
            xb, yb = positions[right][0]
            boxes.append([round(xa + (xb - xa) * ratio, 1), round(ya + (yb - ya) * ratio, 1), round(box_width, 1), round(box_height, 1)])
        else:
            anchor = positions[before[-1]][0] if before else (positions[after[0]][0] if after else (x, y))
            boxes.append([round(float(anchor[0]), 1), round(float(anchor[1]), 1), round(box_width, 1), round(box_height, 1)])
    return boxes


def smooth(boxes, window=2):
    """Median-filter the track so single-frame mis-matches do not make the avatar jitter."""
    array = np.array(boxes, dtype=np.float32)
    if len(array) < 3:
        return boxes
    smoothed = array.copy()
    for index in range(len(array)):
        low = max(0, index - window)
        high = min(len(array), index + window + 1)
        smoothed[index] = np.median(array[low:high], axis=0)
    return [[round(float(value), 1) for value in row] for row in smoothed]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--shape", default="circle", choices=["circle", "rect", "roundrect", "square"])
    parser.add_argument("--box", required=True, help="x,y,w,h of the slot in the first frame")
    parser.add_argument("--search", type=float, default=0.45, help="search window as slot-size ratio")
    parser.add_argument("--smooth", action="store_true", help="median-filter the track")
    parser.add_argument("--json", default="", help="write the boxes to this JSON file")
    args = parser.parse_args()

    frames = load_frames(args.file)
    box = [float(value) for value in args.box.split(",")]
    boxes = track(frames, args.shape, box, args.search)
    if args.smooth:
        boxes = smooth(boxes)
    dx = [item[0] - box[0] for item in boxes]
    dy = [item[1] - box[1] for item in boxes]
    payload = {"file": args.file, "shape": args.shape, "frames": len(frames), "boxes": boxes}
    if args.json:
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    print(
        f"# frames={len(frames)} drift dx={min(dx):.0f}..{max(dx):.0f} dy={min(dy):.0f}..{max(dy):.0f}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
