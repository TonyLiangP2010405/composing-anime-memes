import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/source_candidates.json"


@pytest.fixture
def validator():
    path = ROOT / "scripts/validate_source.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("validate_source", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_candidates


def make_candidate(participants=2):
    return {
        "key": f"scene_{participants}",
        "anime_title": "Example Anime",
        "source_url": "https://example.com/source.gif",
        "gif": "sources/scene.gif",
        "source_type": "anime_episode",
        "origin_confirmed": True,
        "animated": True,
        "motion_preserved": True,
        "participant_count": participants,
        "priority": "preferred" if participants >= 2 else "fallback",
        "casting": ["trigger"]
        if participants == 1
        else ["bot", "trigger"]
        + ["group_affection_random"] * (participants - 2),
    }


def test_multi_person_candidates_and_casting_are_valid(validator):
    manifest = {"candidates": [make_candidate(2), make_candidate(4)]}
    assert validator(manifest) == []


def test_single_person_candidate_is_allowed_only_as_sole_fallback(validator):
    assert validator({"candidates": [make_candidate(1)]}) == []
    manifest = {"candidates": [make_candidate(1), make_candidate(2)]}
    assert "fallback" in " ".join(validator(manifest))


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("key", None, "key"),
        ("anime_title", None, "anime_title"),
        ("anime_title", 123, "anime_title"),
        ("anime_title", False, "anime_title"),
        ("gif", None, "gif"),
        ("source_type", "game", "source_type"),
        ("origin_confirmed", False, "origin_confirmed"),
        ("origin_confirmed", 1, "origin_confirmed"),
        ("source_url", "file:///tmp/source.gif", "source_url"),
        ("source_url", "http://[::1", "source_url"),
        ("anime_title", "", "anime_title"),
        ("motion_preserved", False, "motion_preserved"),
        ("animated", False, "animated"),
        ("participant_count", 0, "participant_count"),
        ("participant_count", None, "participant_count"),
        ("participant_count", "2", "participant_count"),
        ("priority", "unknown", "priority"),
        ("priority", [], "priority"),
        ("gif", "", "gif"),
    ],
)
def test_invalid_source_fields_are_reported(validator, field, value, expected):
    candidate = make_candidate()
    candidate[field] = value
    errors = validator({"candidates": [candidate]})
    assert expected in " ".join(errors)


def test_missing_required_field_is_reported(validator):
    candidate = make_candidate()
    del candidate["anime_title"]
    assert "anime_title" in " ".join(validator({"candidates": [candidate]}))


@pytest.mark.parametrize("participants", [1, 2, 3])
def test_priority_must_match_participant_count(validator, participants):
    candidate = make_candidate(participants)
    candidate["priority"] = "fallback" if participants >= 2 else "preferred"
    assert "priority" in " ".join(validator({"candidates": [candidate]}))


@pytest.mark.parametrize(
    ("participants", "casting"),
    [
        (2, ["trigger", "bot"]),
        (2, ["bot", "trigger", "group_affection_random"]),
        (3, ["bot", "trigger"]),
        (3, ["bot", "trigger", "random"]),
        (4, ["bot", "trigger", "group_affection_random"]),
    ],
)
def test_casting_must_match_fixed_slots(validator, participants, casting):
    candidate = make_candidate(participants)
    candidate["casting"] = casting
    assert "casting" in " ".join(validator({"candidates": [candidate]}))


def write_gif(path, frames):
    images = [Image.new("RGB", (8, 8), color) for color in ("red", "blue")][:frames]
    images[0].save(path, "GIF", save_all=True, append_images=images[1:])


def write_identical_gif(path):
    frame = bytes.fromhex("21F9040000000000 2C000000000100010000 02 02 44 01 00")
    header = bytes.fromhex("474946383961 0100 0100 80 00 00 FF0000 000000")
    path.write_bytes(header + frame + frame + b"\x3b")


def test_real_two_frame_gif_is_accepted_with_relative_path(validator, tmp_path):
    write_gif(tmp_path / "scene.gif", 2)
    candidate = make_candidate()
    candidate["gif"] = "scene.gif"
    errors = validator(
        {"candidates": [candidate]}, base_dir=tmp_path, check_files=True
    )
    assert errors == []


@pytest.mark.parametrize(
    "kind", ["missing", "not_gif", "single_frame", "identical_frames"]
)
def test_invalid_real_gifs_are_rejected(validator, tmp_path, kind):
    path = tmp_path / "scene.gif"
    if kind == "not_gif":
        path.write_text("not a gif", encoding="utf-8")
    elif kind == "single_frame":
        write_gif(path, 1)
    elif kind == "identical_frames":
        write_identical_gif(path)
    candidate = make_candidate()
    candidate["gif"] = "scene.gif"
    errors = validator(
        {"candidates": [candidate]}, base_dir=tmp_path, check_files=True
    )
    assert "gif" in " ".join(errors).lower()


def test_bundled_source_example_is_valid(validator):
    manifest = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert validator(manifest) == []
