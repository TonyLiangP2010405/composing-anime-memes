"""Audit a head-swap template for the "only the avatar is visible" failure.

Coverage checks prove the avatar covers the face.  They do not prove the meme
survives: a 1.22x ellipse on a close-up can swallow the ears, props and
captions, leaving nothing but the user's avatar.  This script scores the base
image and the declared ellipse before rendering.

    python scripts/audit_meme.py --meta /path/to/meta.json --out /tmp/audit.png
    python scripts/audit_meme.py --meta meta.json --strict --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

def face_colors(frame: Image.Image, box: tuple[float, float, float, float]) -> dict[str, float]:
    fx, fy, fw, fh = box
    crop = frame.crop((int(fx), int(fy), int(fx + fw), int(fy + fh))).resize((64, 64))
    pixels = list(crop.getdata())
    total = len(pixels)
    yellow = brown = white = black = 0
    for r, g, b in pixels:
        mx, mn = max(r, g, b), min(r, g, b)
        v = mx / 255
        s = 0 if mx == 0 else (mx - mn) / mx
        if v > 0.68 and s > 0.35 and r > g > b and r - b > 35:
            yellow += 1
        elif 0.28 < v <= 0.72 and s > 0.25 and r > g > b:
            brown += 1
        elif v > 0.85 and s < 0.12:
            white += 1
        elif v < 0.2:
            black += 1
    return {
        "yellow": yellow / total,
        "brown": brown / total,
        "white": white / total,
        "black": black / total,
    }


def theme_of(frame: Image.Image) -> tuple[str, dict[str, float]]:
    small = frame.convert("RGB").resize((48, 48))
    pixels = list(small.getdata())
    total = len(pixels)
    black = sum(1 for r, g, b in pixels if r < 70 and g < 70 and b < 70) / total
    white = sum(1 for r, g, b in pixels if r > 200 and g > 200 and b > 200) / total
    yellow = sum(1 for r, g, b in pixels if r > 150 and g > 120 and b < 110 and r > g) / total
    brown = sum(1 for r, g, b in pixels if r > 90 and g > 50 and b < 80 and r > g > b) / total
    stats = {"black": black, "white": white, "yellow": yellow, "brown": brown}
    if white > 0.20 and black > 0.12:
        return "panda", stats
    if yellow > 0.15:
        return "huaji", stats
    if brown > 0.25:
        return "dog", stats
    return "object", stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("/tmp/audit.png"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures (batch generation)")
    parser.add_argument("--allow-dog", action="store_true", help="accept dog bases as well")
    args = parser.parse_args()

    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    source = args.meta.parent / str(meta["source"])
    with Image.open(source) as image:
        image.seek(0)
        frame = image.convert("RGB")

    width, height = frame.size
    canvas_area = width * height
    fx, fy, fw, fh = meta["face_box"]
    ew, eh = meta.get("ellipse_size") or (meta.get("avatar_size"), meta.get("avatar_size"))
    face_ratio = fw * fh / canvas_area
    ellipse_ratio = ew * eh / canvas_area
    detected = meta.get("detected_face")
    if detected:
        dw, dh = detected[2], detected[3]
        scale = ((ew * eh) / (dw * dh)) ** 0.5
    else:
        scale = 1.0
    theme, stats = theme_of(frame)
    signature = face_colors(frame, (fx, fy, fw, fh))

    warnings: list[str] = []
    failures: list[str] = []
    notes: list[str] = []
    if theme == "dog" and not args.allow_dog:
        failures.append("底图是狗/动物，不是滑稽或熊猫：检测器把狗头当成了脸")
    if theme == "object":
        notes.append("题材无法识别为滑稽/熊猫：可能是摆件/沙雕/卡通头，务必 200px 目视确认")
    if signature["yellow"] > 0.25 and signature["white"] > 0.15 and signature["black"] < 0.20:
        warnings.append(
            "脸框里黄+白混在一起：疑似狗头/黄白玩偶（滑稽脸的白色通常只在眼睛），200px 确认"
        )
    if signature["yellow"] > 0.50 and signature["brown"] > 0.15:
        warnings.append("脸框黄色占比高且带棕色：疑似黄色摆件，不是滑稽脸")
    if not detected:
        notes.append("meta 缺少 detected_face，无法核对椭圆放大倍数；新模板请记录检测框")
    if scale > 1.12:
        warnings.append(f"椭圆比检测框大 {scale:.2f} 倍，容易盖住耳朵/道具/字幕；建议 1.05–1.10")
    if ellipse_ratio > 0.85:
        failures.append(
            f"头像占画面 {ellipse_ratio:.0%}：换完几乎只剩头像，原图角色/道具会消失"
        )
    elif face_ratio > 0.55:
        warnings.append(
            f"特写底图：脸占 {face_ratio:.0%}、头像占 {ellipse_ratio:.0%}；必须确认耳朵/道具/字幕至少两类还能看见"
        )
    elif face_ratio > 0.45 or ellipse_ratio > 0.65:
        warnings.append(
            f"偏特写：脸 {face_ratio:.0%}、头像 {ellipse_ratio:.0%}；逐张确认原图还认得出"
        )

    if args.strict and warnings:
        failures.extend(warnings)
        warnings = []
    verdict = "FAIL" if failures else ("WARN" if warnings else "OK")
    result = {
        "key": meta.get("key"),
        "canvas": [width, height],
        "face_ratio": round(face_ratio, 3),
        "ellipse_ratio": round(ellipse_ratio, 3),
        "scale": round(scale, 2),
        "theme": theme,
        "colors": {k: round(v, 3) for k, v in stats.items()},
        "face_colors": {k: round(v, 3) for k, v in signature.items()},
        "verdict": verdict,
        "failures": failures,
        "warnings": warnings,
        "notes": notes,
        "scale_verified": bool(detected),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return

    draw = ImageDraw.Draw(frame)
    draw.rectangle((fx, fy, fx + fw, fy + fh), outline=(0, 200, 0), width=3)
    draw.ellipse(
        (fx + fw / 2 - ew / 2, fy + fh / 2 - eh / 2, fx + fw / 2 + ew / 2, fy + fh / 2 + eh / 2),
        outline=(255, 0, 0),
        width=3,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.save(args.out)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    print(f"diagnostic: {args.out}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
