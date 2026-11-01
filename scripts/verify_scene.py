"""Mechanical GIF checks; these never replace full-speed visual approval."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

MECHANICAL_ONLY_MESSAGE = "MECHANICAL_ONLY — visual approval still required"


def verify_gif(path, expected_duration=None, max_size=480) -> list[str]:
    try:
        with Image.open(path) as gif:
            if gif.format != "GIF":
                return ["output must be a GIF"]
            errors = []
            if gif.n_frames < 2:
                errors.append("GIF must contain at least two frames")
            if max(gif.size) > max_size:
                errors.append(f"GIF size exceeds {max_size}")
            duration = 0
            digests = set()
            for index in range(gif.n_frames):
                gif.seek(index)
                duration += gif.info.get("duration", 0)
                digests.add(gif.convert("RGB").tobytes())
            if len(digests) < 2:
                errors.append("GIF frames must not all be identical")
            if expected_duration is not None and abs(duration - expected_duration) > 100:
                errors.append(f"GIF duration {duration} differs from expected {expected_duration}")
            return errors
    except (OSError, ValueError) as error:
        return [f"cannot read GIF: {error}"]


def mask_array(path, size) -> np.ndarray:
    with Image.open(path) as mask:
        return np.asarray(mask.convert("L").resize(size, Image.Resampling.BILINEAR)) > 0


def verify_foreground(original, rendered, change_mask) -> list[str]:
    original = original.convert("RGB")
    rendered = rendered.convert("RGB")
    if original.size != rendered.size:
        return ["original and rendered sizes differ"]
    allowed = mask_array(change_mask, original.size)
    if np.array_equal(np.asarray(original)[~allowed], np.asarray(rendered)[~allowed]):
        return []
    return ["pixels outside change_mask were modified"]


def verify_avatar_independence(render_reference, actors, image_count) -> list[str]:
    base = [Image.new("RGB", (80, 80), "white") for _ in range(image_count)]
    neutral = np.asarray(render_reference(base).convert("RGB")).astype(int)
    errors = []
    for index, actor in enumerate(actors):
        avatars = list(base)
        avatars[index] = Image.new("RGB", (80, 80), "#101010")
        output = np.asarray(render_reference(avatars).convert("RGB")).astype(int)
        target = mask_array(actor["change_mask"], (output.shape[1], output.shape[0]))
        changed = np.max(np.abs(output - neutral), axis=2) > 15
        if changed[target].sum() < 25:
            errors.append(f"actors[{index}] does not visibly change its target")
        for other_index, other in enumerate(actors):
            if other_index == index:
                continue
            other_mask = mask_array(other["change_mask"], (output.shape[1], output.shape[0]))
            if not np.array_equal(output[other_mask], neutral[other_mask]):
                errors.append(f"actors[{index}] changes actors[{other_index}] region")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gif", type=Path)
    parser.add_argument("--expected-duration", type=int)
    parser.add_argument("--max-size", type=int, default=480)
    args = parser.parse_args()
    errors = verify_gif(args.gif, args.expected_duration, args.max_size)
    for error in errors:
        print(error)
    print(MECHANICAL_ONLY_MESSAGE)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
