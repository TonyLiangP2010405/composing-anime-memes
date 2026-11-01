import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/character_scene.json"


def load_example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


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
