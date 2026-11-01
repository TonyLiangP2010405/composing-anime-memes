import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/character_scene.json"


def load_example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def write_mask(path, *, mode="L", size=(100, 100), value=255, black_region=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new(mode, size, value)
    if black_region and mode in {"1", "L"}:
        image.paste(0, (0, 0, 10, 10))
    image.save(path)


@pytest.fixture
def validator():
    path = ROOT / "scripts/validate_scene.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("validate_scene", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_scene


def test_character_example_is_valid(validator):
    assert validator(load_example()) == []


def test_character_example_assets_are_valid(validator):
    assert validator(load_example(), base_dir=EXAMPLE.parent) == []


@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (("mode",), None, "mode"),
        (("mode",), "unknown", "mode"),
        (("reference_index",), None, "reference_index"),
        (("actors",), [], "actors"),
        (("actors", 0, "image"), -1, "image"),
        (("actors", 0, "image"), 1, "image"),
        (("actors", 0, "frames"), [], "frames"),
        (("actors", 0, "change_mask"), "", "change_mask"),
        (("actors", 0, "shape"), None, "shape"),
        (("actors", 0, "shape"), "unknown", "shape"),
        (("actors", 0, "shape"), "circle", "shape"),
        (("rectangle_photo",), True, "rectangle_photo"),
    ],
)
def test_invalid_scene_fields_are_reported(validator, path, value, expected):
    config = load_example()
    target = config
    for key in path[:-1]:
        target = target[key]
    if value is None:
        target.pop(path[-1], None)
    else:
        target[path[-1]] = value

    assert expected in " ".join(validator(config))


@pytest.mark.parametrize(
    ("mode", "shape"),
    [
        ("character", "target_mask"),
        ("photo", "quad_fill"),
        ("print", "surface_mask"),
        ("chalk", "target_mask"),
    ],
)
def test_allowed_mode_shape_pairs_are_valid(validator, mode, shape):
    config = load_example()
    config["mode"] = mode
    config["actors"][0]["shape"] = shape
    assert validator(config, base_dir=EXAMPLE.parent) == []


@pytest.mark.parametrize("filename", ["missing.png", "not-an-image.png"])
def test_missing_and_unreadable_masks_are_reported(validator, tmp_path, filename):
    config = load_example()
    mask = tmp_path / "assets/teddy" / filename
    if filename == "not-an-image.png":
        mask.parent.mkdir(parents=True)
        mask.write_text("not an image", encoding="utf-8")
    config["actors"][0]["change_mask"] = f"assets/teddy/{filename}"
    errors = validator(config, base_dir=tmp_path)
    assert "change_mask" in " ".join(errors)


@pytest.mark.parametrize(
    ("mode", "size", "value", "black_region"),
    [
        ("RGB", (100, 100), (255, 255, 255), False),
        ("L", (100, 100), 0, False),
        ("L", (100, 100), 255, False),
        ("L", (99, 100), 255, True),
    ],
)
def test_mask_format_contents_and_size_are_validated(
    validator, tmp_path, mode, size, value, black_region
):
    config = load_example()
    for name in ("change-00.png", "change-01.png"):
        write_mask(tmp_path / "assets/teddy" / name)
    write_mask(
        tmp_path / "assets/teddy/change-00.png",
        mode=mode,
        size=size,
        value=value,
        black_region=black_region,
    )
    errors = validator(config, base_dir=tmp_path)
    assert "change_mask" in " ".join(errors)


@pytest.mark.parametrize("shape", ["target_mask", "surface_mask"])
def test_target_shapes_require_frame_masks(validator, shape):
    config = load_example()
    config["mode"] = "character" if shape == "target_mask" else "print"
    config["actors"][0]["shape"] = shape
    config["actors"][0]["frames"][0].pop("mask")
    errors = validator(config, base_dir=EXAMPLE.parent)
    assert "frames[0].mask" in " ".join(errors)


@pytest.mark.parametrize(
    "source_size",
    [None, [100], [100, 0], [100, True], (100, 100), "100x100"],
)
def test_source_size_is_required_for_mask_dimension_validation(validator, source_size):
    config = load_example()
    if source_size is None:
        config.pop("source_size")
    else:
        config["source_size"] = source_size
    errors = validator(config, base_dir=EXAMPLE.parent)
    assert "source_size" in " ".join(errors)


@pytest.mark.parametrize("field", ["change_mask", "frame_mask"])
def test_non_string_mask_paths_are_reported_without_raising(validator, field):
    config = load_example()
    if field == "change_mask":
        config["actors"][0]["change_mask"] = 123
    else:
        config["actors"][0]["frames"][0]["mask"] = 123
    errors = validator(config, base_dir=EXAMPLE.parent)
    assert "mask" in " ".join(errors)


@pytest.mark.parametrize(
    "quad",
    [
        None,
        [[0, 0], [10, 0], [10, 10]],
        [[0, 0], [10, 0], [10, 10], [float("nan"), 10]],
        [[0, 0], [10, 0], [10, 10], [10**10000, 10]],
        [[0, 0], [10, 0], [20, 0], [30, 0]],
        [[0, 0], [10, 0], [10, 10], [10, 10]],
        [[0, 0], [20, 20], [0, 10], [10, 0]],
    ],
)
def test_quad_fill_requires_four_finite_nondegenerate_vertices(validator, quad):
    config = load_example()
    config["mode"] = "photo"
    config["actors"][0]["shape"] = "quad_fill"
    if quad is None:
        config["actors"][0]["frames"][0].pop("quad")
    else:
        config["actors"][0]["frames"][0]["quad"] = quad
    errors = validator(config, base_dir=EXAMPLE.parent)
    assert "frames[0].quad" in " ".join(errors)


@pytest.mark.parametrize("location", ["actor", "frame"])
def test_foreground_mask_file_is_validated(validator, location):
    config = load_example()
    if location == "actor":
        config["actors"][0]["foreground_mask"] = "assets/teddy/missing.png"
    else:
        config["actors"][0]["frames"][0]["foreground_mask"] = "assets/teddy/missing.png"
    errors = validator(config, base_dir=EXAMPLE.parent)
    assert "foreground_mask" in " ".join(errors)


def test_full_frame_foreground_mask_is_rejected(validator, tmp_path):
    config = load_example()
    for name in ("change-00.png", "change-01.png"):
        write_mask(tmp_path / "assets/teddy" / name)
    write_mask(
        tmp_path / "assets/teddy/foreground.png",
        value=255,
        black_region=False,
    )
    config["actors"][0]["foreground_mask"] = "assets/teddy/foreground.png"
    errors = validator(config, base_dir=tmp_path)
    assert "foreground_mask" in " ".join(errors)


def test_completed_scene_requires_visual_approval(validator):
    config = load_example()
    assert "visual_approval" in " ".join(validator(config, completed=True))


def test_approval_hashes_must_be_complete_hex_sha256(validator):
    config = load_example()
    config["visual_approval"] = {
        "reviewer": "user",
        "approved": True,
        "sha256": "not-a-hash",
        "source_sha256": "0" * 64,
    }
    assert "sha256" in " ".join(validator(config, completed=True))


def test_valid_approval_is_accepted(validator):
    config = load_example()
    config["visual_approval"] = {
        "reviewer": "user",
        "approved": True,
        "sha256": "a" * 64,
        "source_sha256": "b" * 64,
    }
    assert validator(config, completed=True) == []


def test_reject_requires_reason_and_cannot_be_approved(validator):
    config = load_example()
    config["mode"] = "reject"
    assert "reason" in " ".join(validator(config))
    config["reason"] = "头像无法参与场景动作"
    config["visual_approval"]["approved"] = True
    assert "reject" in " ".join(validator(config, completed=True))
