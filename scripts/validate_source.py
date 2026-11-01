"""Validate anime GIF candidate records and optional real GIF files."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

REQUIRED_FIELDS = (
    "key",
    "anime_title",
    "source_url",
    "gif",
    "source_type",
    "origin_confirmed",
    "animated",
    "motion_preserved",
    "participant_count",
    "priority",
    "casting",
)


def validate_candidates(
    manifest: dict, *, base_dir: Path | None = None, check_files: bool = False
) -> list[str]:
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ["candidates must be a non-empty list"]

    errors = []

    def is_preferred_multi_person(candidate) -> bool:
        if not isinstance(candidate, dict) or candidate.get("priority") != "preferred":
            return False
        count = candidate.get("participant_count")
        return not isinstance(count, bool) and isinstance(count, int) and count >= 2

    has_multi_person = any(is_preferred_multi_person(candidate) for candidate in candidates)
    for index, candidate in enumerate(candidates):
        prefix = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in REQUIRED_FIELDS:
            if field not in candidate:
                errors.append(f"{prefix}.{field} is required")
        for field in ("key", "anime_title", "gif"):
            value = candidate.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        try:
            url = urlparse(str(candidate.get("source_url", "")))
            valid_url = url.scheme in {"http", "https"} and bool(url.netloc)
        except ValueError:
            valid_url = False
        if not valid_url:
            errors.append(f"{prefix}.source_url must be an HTTP(S) URL")
        if candidate.get("source_type") != "anime_episode":
            errors.append(f"{prefix}.source_type must be anime_episode")
        for field in ("origin_confirmed", "animated", "motion_preserved"):
            if candidate.get(field) is not True:
                errors.append(f"{prefix}.{field} must be true")

        participants = candidate.get("participant_count")
        valid_count = (
            not isinstance(participants, bool)
            and isinstance(participants, int)
            and participants > 0
        )
        if not valid_count:
            errors.append(f"{prefix}.participant_count must be a positive integer")
        priority = candidate.get("priority")
        if not isinstance(priority, str) or priority not in {"preferred", "fallback"}:
            errors.append(f"{prefix}.priority must be preferred or fallback")
        elif valid_count:
            expected_priority = "preferred" if participants >= 2 else "fallback"
            if priority != expected_priority:
                errors.append(f"{prefix}.priority does not match participant_count")
            if participants == 1 and has_multi_person:
                errors.append(f"{prefix} single-person fallback has multi-person candidates")

        if valid_count:
            expected_casting = (
                ["trigger"]
                if participants == 1
                else ["bot", "trigger"]
                + ["group_affection_random"] * (participants - 2)
            )
            if candidate.get("casting") != expected_casting:
                errors.append(f"{prefix}.casting does not match participant_count")

        gif_field = candidate.get("gif")
        gif_value = gif_field.strip() if isinstance(gif_field, str) else ""
        if gif_value and not gif_value.lower().endswith(".gif"):
            errors.append(f"{prefix}.gif must name a GIF file")
        if check_files and gif_value:
            gif_path = Path(gif_value)
            if not gif_path.is_absolute():
                gif_path = (base_dir or Path.cwd()) / gif_path
            try:
                with Image.open(gif_path) as gif:
                    if gif.format != "GIF":
                        errors.append(f"{prefix}.gif must be a GIF")
                    elif gif.n_frames < 2:
                        errors.append(f"{prefix}.gif must contain at least two frames")
                    else:
                        digests = set()
                        for frame_index in range(gif.n_frames):
                            gif.seek(frame_index)
                            digests.add(gif.convert("RGB").tobytes())
                        if len(digests) < 2:
                            errors.append(f"{prefix}.gif frames must not all be identical")
            except (OSError, ValueError) as error:
                errors.append(f"{prefix}.gif cannot be read: {error}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = validate_candidates(
        manifest, base_dir=args.manifest.parent, check_files=args.check_files
    )
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("SOURCES_VALID")


if __name__ == "__main__":
    main()
