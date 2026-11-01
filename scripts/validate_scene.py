"""Validate scene composition and visual-approval contracts."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from PIL import Image

MODES = {"character", "print", "photo", "chalk", "reject"}
MODE_SHAPES = {
    "character": "target_mask",
    "print": "surface_mask",
    "photo": "quad_fill",
    "chalk": "target_mask",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def cross(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a, b, point) -> bool:
    return (
        min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
    )


def segments_intersect(a, b, c, d) -> bool:
    first = cross(a, b, c)
    second = cross(a, b, d)
    third = cross(c, d, a)
    fourth = cross(c, d, b)
    if first * second < 0 and third * fourth < 0:
        return True
    return (
        (first == 0 and on_segment(a, b, c))
        or (second == 0 and on_segment(a, b, d))
        or (third == 0 and on_segment(c, d, a))
        or (fourth == 0 and on_segment(c, d, b))
    )


def valid_quad(quad) -> bool:
    if not isinstance(quad, list) or len(quad) != 4:
        return False
    try:
        points = []
        for point in quad:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                return False
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in point
            ):
                return False
            coordinates = (float(point[0]), float(point[1]))
            if not all(math.isfinite(value) for value in coordinates):
                return False
            points.append(coordinates)
    except (OverflowError, TypeError, ValueError):
        return False
    if len(set(points)) != 4:
        return False
    if segments_intersect(points[0], points[1], points[2], points[3]):
        return False
    if segments_intersect(points[1], points[2], points[3], points[0]):
        return False
    area = sum(
        points[index][0] * points[(index + 1) % 4][1]
        - points[(index + 1) % 4][0] * points[index][1]
        for index in range(4)
    )
    return math.isfinite(area) and not math.isclose(area, 0.0, abs_tol=1e-9)


def validate_mask(path, field, source_size, require_black, base_dir, errors) -> None:
    if base_dir is None:
        return
    if not isinstance(path, (str, Path)) or not str(path).strip():
        errors.append(f"{field} must be a mask path string")
        return
    try:
        mask_path = Path(path)
        if not mask_path.is_absolute():
            mask_path = base_dir / mask_path
        with Image.open(mask_path) as image:
            image.load()
            if image.mode not in {"1", "L"}:
                errors.append(f"{field} must be a grayscale mask")
                return
            if source_size is not None and list(image.size) != source_size:
                errors.append(f"{field} dimensions must match source_size")
            minimum, maximum = image.getextrema()
            if maximum <= 0:
                errors.append(f"{field} must contain a non-empty white region")
            if require_black and minimum > 0:
                errors.append(f"{field} must preserve some black source pixels")
    except (OSError, TypeError, ValueError, SyntaxError) as error:
        errors.append(f"{field} is not a readable mask: {error}")


def validate_scene(
    config: dict, *, completed: bool = False, base_dir: Path | None = None
) -> list[str]:
    if not isinstance(config, dict):
        return ["config must be an object"]
    errors = []
    mode = config.get("mode")
    if mode not in MODES:
        errors.append("mode must be character, print, photo, chalk, or reject")
    if config.get("rectangle_photo") and mode != "photo":
        errors.append("rectangle_photo is only valid for photo scenes")
    if mode == "reject":
        if not str(config.get("reason", "")).strip():
            errors.append("reject scenes require a reason")
        if completed and config.get("visual_approval", {}).get("approved"):
            errors.append("reject scenes cannot receive visual approval")
        return errors
    source_size = config.get("source_size")
    if (
        not isinstance(source_size, list)
        or len(source_size) != 2
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in source_size
        )
    ):
        errors.append("source_size must contain two positive integers")
        source_size = None
    reference = config.get("reference_index")
    if isinstance(reference, bool) or not isinstance(reference, int) or reference < 0:
        errors.append("reference_index must be a non-negative integer")
    actors = config.get("actors")
    if not isinstance(actors, list) or not actors:
        errors.append("actors must be a non-empty list")
        actors = []
    image_count = config.get("image_count", len(actors))
    expected_shape = MODE_SHAPES.get(mode)
    for index, actor in enumerate(actors):
        image = actor.get("image")
        if isinstance(image, bool) or not isinstance(image, int) or not 0 <= image < image_count:
            errors.append(f"actors[{index}].image is out of range")
        if actor.get("shape") != expected_shape:
            errors.append(f"actors[{index}].shape must be {expected_shape}")
        frames = actor.get("frames")
        if not isinstance(frames, list) or not frames:
            errors.append(f"actors[{index}].frames must be a non-empty list")
        else:
            for frame_index, frame in enumerate(frames):
                value = frame.get("index")
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    errors.append(f"actors[{index}].frames[{frame_index}].index is invalid")
                field = f"actors[{index}].frames[{frame_index}]"
                if expected_shape == "quad_fill" and not valid_quad(frame.get("quad")):
                    errors.append(f"{field}.quad must contain four finite, non-degenerate vertices")
                if expected_shape in {"target_mask", "surface_mask"}:
                    mask = frame.get("mask")
                    if not str(mask or "").strip():
                        errors.append(f"{field}.mask is required")
                    else:
                        validate_mask(
                            mask,
                            f"{field}.mask",
                            source_size,
                            True,
                            base_dir,
                            errors,
                        )
        change_mask = actor.get("change_mask")
        if not str(change_mask or "").strip():
            errors.append(f"actors[{index}].change_mask is required")
        else:
            validate_mask(
                change_mask,
                f"actors[{index}].change_mask",
                source_size,
                expected_shape in {"target_mask", "surface_mask"},
                base_dir,
                errors,
            )
    approval = config.get("visual_approval")
    if completed and (not isinstance(approval, dict) or not approval.get("approved")):
        errors.append("visual_approval.approved must be true for completed scenes")
    if isinstance(approval, dict) and approval.get("approved"):
        if not str(approval.get("reviewer", "")).strip():
            errors.append("visual_approval.reviewer is required")
        for field in ("sha256", "source_sha256"):
            if not SHA256.fullmatch(str(approval.get(field, ""))):
                errors.append(f"visual_approval.{field} must be a 64-character hex SHA256")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--completed", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    errors = validate_scene(
        config, completed=args.completed, base_dir=args.config.resolve().parent
    )
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("SCENE_VALID")


if __name__ == "__main__":
    main()
