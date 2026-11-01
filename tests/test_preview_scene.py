import hashlib
import importlib.util
import json
from io import BytesIO
from pathlib import Path

import meme_generator
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TEST_KEY = "skill_preview_real_backend_example"


def load_module():
    path = ROOT / "scripts/preview_scene.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("preview_scene", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def preview():
    return load_module()


def png_bytes(color="red"):
    output = BytesIO()
    Image.new("RGB", (32, 32), color).save(output, "PNG")
    return output.getvalue()


def write_gif(path, colors=("red", "green", "blue", "yellow", "white")):
    frames = [Image.new("RGB", (40, 40), color) for color in colors]
    frames[0].save(path, "GIF", save_all=True, append_images=frames[1:], duration=50, loop=0)
    return path


@pytest.fixture(scope="session", autouse=True)
def register_real_backend():
    def render(images, texts, args):
        output = BytesIO()
        frames = [Image.new("RGB", (40, 40), "red"), Image.new("RGB", (40, 40), "blue")]
        frames[0].save(output, "GIF", save_all=True, append_images=frames[1:], duration=50, loop=0)
        output.seek(0)
        return output

    meme_generator.add_meme(TEST_KEY, render, min_images=1, max_images=1, min_texts=0, max_texts=0)


def config():
    data = json.loads((ROOT / "examples/character_scene.json").read_text(encoding="utf-8"))
    data["key"] = TEST_KEY
    return data


def test_preview_without_baseline_uses_untouched_source(preview, tmp_path):
    source = write_gif(tmp_path / "source.gif")
    result = preview.preview_scene(
        config(), meme_generator, tmp_path / "out", [png_bytes()], source=source
    )

    assert result["kind"] == "original"
    assert result["before_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_preview_rework_requires_saved_baseline(preview, tmp_path):
    source = write_gif(tmp_path / "source.gif")
    with pytest.raises(FileNotFoundError):
        preview.preview_scene(
            config(),
            meme_generator,
            tmp_path / "out",
            [png_bytes()],
            baseline=tmp_path / "missing.gif",
            source=source,
        )


def test_triptych_uses_scene_reference_frame(preview, tmp_path):
    source = write_gif(tmp_path / "source.gif")
    destination = tmp_path / "triptych.jpg"

    preview.write_triptych(source, destination, reference_frame=3)

    with Image.open(destination) as image:
        red, green, blue = image.getpixel((480, 110))
    assert red > 200 and green > 200 and blue < 50


def test_preview_calls_real_backend_and_records_sha256(preview, tmp_path):
    source = write_gif(tmp_path / "source.gif")
    result = preview.preview_scene(
        config(), meme_generator, tmp_path / "out", [png_bytes()], source=source
    )

    after = tmp_path / "out" / "after.gif"
    assert after.is_file()
    assert result["after_sha256"] == hashlib.sha256(after.read_bytes()).hexdigest()
    assert result["visual_approval_required"] is True
    metadata = json.loads((tmp_path / "out" / "preview.json").read_text(encoding="utf-8"))
    assert metadata["after_sha256"] == result["after_sha256"]
