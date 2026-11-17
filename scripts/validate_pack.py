"""Validate a standard-shape meme template pack.

Checks a `scenes.json` (plus its assets) against the slot contract:

* every slot uses a supported shape and a box inside the source artwork;
* the artwork exists, its size and SHA-256 match the scene;
* every frame index is inside the animation;
* the pack renders through meme-generator's renderer and produces a sane image;
* an avatar actually lands inside each slot (dark vs light avatar test).

    python scripts/validate_pack.py path/to/memes/mantou_stickers

Exit code 0 means MECHANICAL_ONLY: it does not certify visual quality.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SHAPES = {"ellipse", "circle", "rect", "roundrect", "polygon"}
MAX_SIDE = 480


def make_avatar(colour: tuple[int, int, int], size: int = 256) -> Image.Image:
    image = Image.new("RGB", (size, size), tuple(255 - channel for channel in colour))
    draw = ImageDraw.Draw(image)
    draw.ellipse((size * 0.18, size * 0.12, size * 0.82, size * 0.78), fill=colour)
    return image


def load_renderer(module: Path):
    spec = importlib.util.spec_from_file_location("_validate_pack_render", module / "render.py")
    renderer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = renderer
    spec.loader.exec_module(renderer)
    return renderer


def check_geometry(scene: dict, errors: list[str]) -> None:
    width, height = scene["source_size"]
    for slot in scene["slots"]:
        shape = slot.get("shape", "ellipse")
        if shape not in SHAPES:
            errors.append(f"{scene['key']}: unsupported shape {shape}")
        box = slot.get("box") or (slot.get("boxes") or [[0, 0, 0, 0]])[0]
        x, y, box_width, box_height = box
        if box_width < 8 or box_height < 8:
            errors.append(f"{scene['key']}: slot box too small {box}")
        if x < 0 or y < 0 or x + box_width > width or y + box_height > height:
            errors.append(f"{scene['key']}: slot box {box} outside {width}x{height}")
        if "boxes" in slot and len(slot["boxes"]) != len(scene["frames"]):
            errors.append(f"{scene['key']}: per-frame boxes do not match frames")
        for key in ("zoom", "feather"):
            if key in slot and slot[key] < 0:
                errors.append(f"{scene['key']}: negative {key}")


def check_assets(scene: dict, module: Path, errors: list[str]) -> None:
    path = module / scene["source"]
    if not path.exists():
        errors.append(f"{scene['key']}: missing artwork {scene['source']}")
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if scene.get("source_sha256") and digest != scene["source_sha256"]:
        errors.append(f"{scene['key']}: sha256 mismatch for {scene['source']}")
    with Image.open(path) as image:
        frames = getattr(image, "n_frames", 1)
        if list(image.size) != list(scene["source_size"]):
            errors.append(
                f"{scene['key']}: source_size {scene['source_size']} != {list(image.size)}"
            )
    for item in scene["frames"]:
        if not 0 <= item["index"] < frames:
            errors.append(f"{scene['key']}: frame index {item['index']} >= {frames}")
    for slot in scene["slots"]:
        if slot.get("image", 0) >= scene["images"]:
            errors.append(f"{scene['key']}: slot image index out of range")


def check_render(scene: dict, renderer, errors: list[str]) -> None:
    dark = make_avatar((8, 8, 8))
    light = make_avatar((247, 247, 247))
    dark_bytes = renderer.render(scene, [dark]).getvalue()
    light_bytes = renderer.render(scene, [light]).getvalue()
    if not dark_bytes:
        errors.append(f"{scene['key']}: renderer produced no data")
        return
    with Image.open(io.BytesIO(dark_bytes)) as image:
        if max(image.size) > MAX_SIDE:
            errors.append(f"{scene['key']}: output larger than {MAX_SIDE}px")
    if dark_bytes == light_bytes:
        errors.append(f"{scene['key']}: avatar has no effect on output")
        return
    dark_image = Image.open(io.BytesIO(dark_bytes)).convert("RGB")
    light_image = Image.open(io.BytesIO(light_bytes)).convert("RGB")
    scale = dark_image.width / scene["source_size"][0]
    for slot in scene["slots"]:
        x, y, width, height = [value * scale for value in slot["box"]]
        inset = 0.34 if slot.get("shape", "ellipse") in {"ellipse", "circle"} else 0.2
        box = (
            round(x + width * inset),
            round(y + height * inset),
            round(x + width * (1 - inset)),
            round(y + height * (1 - inset)),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            errors.append(f"{scene['key']}: empty sampling box for slot")
            continue
        dark_crop = dark_image.crop(box).convert("L")
        light_crop = light_image.crop(box).convert("L")
        dark_mean = sum(dark_crop.getdata()) / (dark_crop.width * dark_crop.height)
        light_mean = sum(light_crop.getdata()) / (light_crop.width * light_crop.height)
        if light_mean - dark_mean <= 60:
            errors.append(f"{scene['key']}: avatar does not land inside the slot")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module", help="folder holding scenes.json, render.py and assets/")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    args = parser.parse_args()
    module = Path(args.module).resolve()
    scenes_path = module / "scenes.json"
    if not scenes_path.exists():
        print(f"FAIL no scenes.json in {module}")
        return 1
    scenes = json.loads(scenes_path.read_text(encoding="utf-8"))
    renderer = load_renderer(module)
    errors: list[str] = []
    for scene in scenes:
        check_geometry(scene, errors)
        check_assets(scene, module, errors)
        try:
            check_render(scene, renderer, errors)
        except Exception as error:  # noqa: BLE001
            errors.append(f"{scene['key']}: render failed: {error}")
    report = {
        "scenes": len(scenes),
        "errors": errors,
        "status": "MECHANICAL_ONLY" if not errors else "FAIL",
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        for error in errors:
            print("FAIL", error)
        print(f"{report['status']}: {len(scenes)} scenes, {len(errors)} problem(s)")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
