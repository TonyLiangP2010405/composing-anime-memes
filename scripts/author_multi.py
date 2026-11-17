"""Author a multi-person template: one artwork, several slots, one avatar per slot.

Group memes often have more than one replaceable area - a TV screen plus the panda's blank head,
two light bulbs, two characters' faces, three phone screens.  This tool writes such a scene and
copies the artwork, so `images=2/3` templates can be rendered with one avatar per slot.

    python tools/author_multi.py --id 0020 --title 群友看电视 --file meme.gif \
        --slot "rect:86,90,371,291" --slot "circle:422,247,192,192"

Slots are rendered with avatar 1, 2, ... in the order given.  `--track` tracks every slot across
the animation frames.
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "memes/mantou_stickers"
SCENES = MODULE / "scenes.json"
ASSETS = MODULE / "assets"


def parse_slot(text):
    shape, numbers = text.split(":", 1)
    box = [float(value) for value in numbers.split(",")]
    if len(box) != 4:
        raise SystemExit(f"slot needs 4 numbers: {text}")
    return {"shape": shape, "box": box}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--slot", action="append", required=True, help="shape:x,y,w,h (repeatable)")
    parser.add_argument("--radius", type=float, help="corner radius for roundrect slots")
    parser.add_argument("--zoom", type=float, default=1.0)
    parser.add_argument("--feather", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=24)
    parser.add_argument("--track", action="store_true")
    args = parser.parse_args()

    source = Path(args.file)
    asset_dir = ASSETS / args.id
    asset_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".gif" if source.suffix.lower() == ".gif" else ".jpg"
    target = asset_dir / f"source{suffix}"
    if suffix == ".jpg":
        Image.open(source).convert("RGB").save(target, quality=95, subsampling=0)
    else:
        shutil.copyfile(source, target)
    data = target.read_bytes()

    with Image.open(target) as image:
        image.seek(0)
        size = list(image.size)
        frames = getattr(image, "n_frames", 1)
        durations = []
        if frames > 1:
            indices = list(range(frames))
            if frames > args.max_frames:
                import numpy as np

                indices = sorted(set(round(value) for value in np.linspace(0, frames - 1, args.max_frames)))
            for index in indices:
                image.seek(index)
                per = int(image.info.get("duration", 60)) or 60
                durations.append(per * max(1, round(frames / max(1, len(indices)))))
        else:
            indices = [0]
            durations = [0]

    slots = []
    for position, text in enumerate(args.slot):
        slot = parse_slot(text)
        left = max(0.0, slot["box"][0])
        top = max(0.0, slot["box"][1])
        right = min(float(size[0]), slot["box"][0] + slot["box"][2])
        bottom = min(float(size[1]), slot["box"][1] + slot["box"][3])
        slot["box"] = [round(left, 1), round(top, 1), round(right - left, 1), round(bottom - top, 1)]
        slot["image"] = position
        slot["feather"] = args.feather
        if args.zoom != 1.0:
            slot["zoom"] = args.zoom
        if slot["shape"] == "roundrect" and args.radius:
            slot["radius"] = args.radius
        slots.append(slot)

    if args.track and frames > 1:
        sys.path.insert(0, str(ROOT / "tools"))
        from track_slots import load_frames, track  # noqa: PLC0415

        all_frames = load_frames(target)
        selected = [all_frames[index] for index in indices]
        for slot in slots:
            slot["boxes"] = track(selected, "circle" if slot["shape"] == "circle" else "rect", slot["box"])

    scene = {
        "key": f"mantou_sticker_{args.id}",
        "title": args.title,
        "source": f"assets/{args.id}/{target.name}",
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_size": size,
        "images": len(slots),
        "frames": [{"index": index, "duration": durations[position]} for position, index in enumerate(indices)],
        "slots": slots,
    }
    scenes = json.loads(SCENES.read_text(encoding="utf-8")) if SCENES.exists() else []
    scenes = [item for item in scenes if item["key"] != scene["key"]]
    scenes.append(scene)
    scenes.sort(key=lambda item: item["key"])
    SCENES.write_text(json.dumps(scenes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(scene, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
