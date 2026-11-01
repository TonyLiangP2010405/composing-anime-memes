import importlib.util
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def verifier():
    path = ROOT / "scripts/verify_scene.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("verify_scene", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_gif(path, size=(100, 100), frames=2, duration=50, mode="RGB"):
    images = [Image.new(mode, size, "red"), Image.new(mode, size, "blue")][:frames]
    images[0].save(path, "GIF", save_all=True, append_images=images[1:], duration=duration, loop=0)


def test_valid_gif_and_transparent_extreme_ratio_are_accepted(verifier, tmp_path):
    path = tmp_path / "valid.gif"
    write_gif(path)
    assert verifier.verify_gif(path, expected_duration=100) == []
    extreme = tmp_path / "extreme.gif"
    write_gif(extreme, size=(1, 480), mode="RGBA")
    assert verifier.verify_gif(extreme, max_size=480) == []


@pytest.mark.parametrize("kind", ["single", "size", "duration", "broken"])
def test_invalid_gifs_are_reported(verifier, tmp_path, kind):
    path = tmp_path / f"{kind}.gif"
    if kind == "broken":
        path.write_text("not a gif")
    else:
        write_gif(
            path,
            size=(500, 500) if kind == "size" else (100, 100),
            frames=1 if kind == "single" else 2,
        )
    expected = 201 if kind == "duration" else None
    assert verifier.verify_gif(path, expected_duration=expected)


def masks(tmp_path):
    left = Image.new("L", (100, 100), 0)
    right = Image.new("L", (100, 100), 0)
    left.paste(255, (0, 0, 40, 100))
    right.paste(255, (60, 0, 100, 100))
    left.save(tmp_path / "left.png")
    right.save(tmp_path / "right.png")
    return [
        {"change_mask": str(tmp_path / "left.png")},
        {"change_mask": str(tmp_path / "right.png")},
    ]


def test_avatar_independence_rejects_cross_actor_bleed(verifier, tmp_path):
    def broken(images):
        value = images[0].getpixel((0, 0))[0]
        return Image.new("RGB", (100, 100), (value, value, value))

    assert verifier.verify_avatar_independence(broken, masks(tmp_path), 2)


def test_avatar_independence_accepts_isolated_regions(verifier, tmp_path):
    def isolated(images):
        canvas = Image.new("RGB", (100, 100), "white")
        for index, image in enumerate(images):
            box = (0, 0, 40, 100) if index == 0 else (60, 0, 100, 100)
            canvas.paste(image.getpixel((0, 0)), box)
        return canvas

    assert verifier.verify_avatar_independence(isolated, masks(tmp_path), 2) == []


def test_foreground_changes_outside_mask_are_rejected(verifier, tmp_path):
    mask = Image.new("L", (100, 100), 0)
    mask.paste(255, (0, 0, 40, 100))
    mask_path = tmp_path / "mask.png"
    mask.save(mask_path)
    original = Image.new("RGB", (100, 100), "black")
    allowed = original.copy()
    allowed.paste("white", (0, 0, 40, 100))
    assert verifier.verify_foreground(original, allowed, mask_path) == []
    broken = allowed.copy()
    broken.putpixel((80, 80), (255, 255, 255))
    assert verifier.verify_foreground(original, broken, mask_path)


def test_mechanical_message_does_not_claim_visual_approval(verifier):
    assert "visual approval still required" in verifier.MECHANICAL_ONLY_MESSAGE
