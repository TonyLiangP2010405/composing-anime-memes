"""Tests for scripts/validate_pack.py."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts/validate_pack.py"

RENDER = textwrap.dedent(
    '''
    """Minimal slot renderer used by the validator test fixture."""

    from io import BytesIO

    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter


    def render(scene, images):
        width, height = scene["source_size"]
        frame = Image.new("RGB", (width, height), "white")
        avatar = images[0].convert("RGB")
        for slot in scene["slots"]:
            x, y, box_width, box_height = [int(round(value)) for value in slot["box"]]
            mask = Image.new("L", (box_width * 4, box_height * 4), 0)
            ImageDraw.Draw(mask).ellipse(
                (0, 0, box_width * 4 - 1, box_height * 4 - 1), fill=255
            )
            mask = mask.resize((box_width, box_height), Image.Resampling.LANCZOS)
            mask = mask.filter(ImageFilter.GaussianBlur(1.0))
            patch = avatar.resize((box_width, box_height), Image.Resampling.LANCZOS)
            frame.paste(patch, (x, y), mask)
        buffer = BytesIO()
        frame.save(buffer, "JPEG", quality=90)
        buffer.seek(0)
        return buffer
    '''
)


def build_pack(folder: Path, box, shape="ellipse"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "render.py").write_text(RENDER, encoding="utf-8")
    artwork = folder / "asset.jpg"
    Image.new("RGB", (300, 300), (30, 30, 30)).save(artwork, quality=95)
    import hashlib

    scene = {
        "key": "demo_0001",
        "title": "demo",
        "source": "asset.jpg",
        "source_sha256": hashlib.sha256(artwork.read_bytes()).hexdigest(),
        "source_size": [300, 300],
        "images": 1,
        "frames": [{"index": 0, "duration": 0}],
        "slots": [{"image": 0, "shape": shape, "box": box}],
    }
    (folder / "scenes.json").write_text(json.dumps([scene], ensure_ascii=False), encoding="utf-8")


def run(folder: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(folder), "--json"],
        capture_output=True,
        text=True,
    )


def test_valid_pack_passes(tmp_path):
    build_pack(tmp_path / "pack", [60.0, 60.0, 180.0, 180.0])
    result = run(tmp_path / "pack")
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "MECHANICAL_ONLY"
    assert report["errors"] == []


def test_box_outside_artwork_fails(tmp_path):
    build_pack(tmp_path / "pack", [200.0, 200.0, 180.0, 180.0])
    result = run(tmp_path / "pack")
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert any("outside" in error for error in report["errors"])


def test_hash_mismatch_fails(tmp_path):
    build_pack(tmp_path / "pack", [60.0, 60.0, 180.0, 180.0])
    scenes_path = tmp_path / "pack" / "scenes.json"
    scenes = json.loads(scenes_path.read_text(encoding="utf-8"))
    scenes[0]["source_sha256"] = "0" * 64
    scenes_path.write_text(json.dumps(scenes), encoding="utf-8")
    result = run(tmp_path / "pack")
    assert result.returncode == 1
    assert any("sha256" in error for error in json.loads(result.stdout)["errors"])
