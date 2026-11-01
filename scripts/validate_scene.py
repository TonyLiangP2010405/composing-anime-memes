"""Validate scene composition and visual-approval contracts."""

import argparse
import json
import re
from pathlib import Path

MODES = {"character", "print", "photo", "chalk", "reject"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_scene(config: dict, *, completed: bool = False) -> list[str]:
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
    reference = config.get("reference_index")
    if isinstance(reference, bool) or not isinstance(reference, int) or reference < 0:
        errors.append("reference_index must be a non-negative integer")
    actors = config.get("actors")
    if not isinstance(actors, list) or not actors:
        errors.append("actors must be a non-empty list")
        actors = []
    image_count = config.get("image_count", len(actors))
    for index, actor in enumerate(actors):
        image = actor.get("image")
        if isinstance(image, bool) or not isinstance(image, int) or not 0 <= image < image_count:
            errors.append(f"actors[{index}].image is out of range")
        frames = actor.get("frames")
        if not isinstance(frames, list) or not frames:
            errors.append(f"actors[{index}].frames must be a non-empty list")
        else:
            for frame_index, frame in enumerate(frames):
                value = frame.get("index")
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    errors.append(f"actors[{index}].frames[{frame_index}].index is invalid")
        if not str(actor.get("change_mask", "")).strip():
            errors.append(f"actors[{index}].change_mask is required")
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
    errors = validate_scene(config, completed=args.completed)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("SCENE_VALID")


if __name__ == "__main__":
    main()
