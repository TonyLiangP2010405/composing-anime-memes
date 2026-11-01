"""Generate real-backend GIF previews without inventing baselines."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_position(config) -> int | None:
    reference = config["reference_index"]
    return next(
        (index for index, frame in enumerate(config["frames"]) if frame["index"] == reference),
        None,
    )


def write_triptych(source: Path, destination: Path, reference_frame=None) -> None:
    canvas = Image.new("RGB", (960, 220), "white")
    with Image.open(source) as gif:
        middle = gif.n_frames // 2 if reference_frame is None else reference_frame
        middle = min(max(middle, 0), gif.n_frames - 1)
        for column, index in enumerate((0, middle, gif.n_frames - 1)):
            gif.seek(index)
            frame = gif.convert("RGB").resize((320, 220), Image.Resampling.LANCZOS)
            canvas.paste(frame, (column * 320, 0))
    canvas.save(destination, quality=95, subsampling=0)


def write_html(output_dir: Path, kind: str) -> None:
    label = "原片（无旧版）" if kind == "original" else "改进前"
    page = f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>场景预览</title>
<style>body{{font:16px/1.6 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;
background:#edf0f5;color:#283747}}
main{{max-width:1100px;margin:auto;padding:24px}}
section{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
img{{width:100%;background:white}}
@media(max-width:650px){{section{{grid-template-columns:1fr}}}}</style>
<main><h1>真实后端 GIF 对照</h1><section>
<figure><figcaption>{label}</figcaption><img src='before.gif'></figure>
<figure><figcaption>本次渲染</figcaption><img src='after.gif'></figure></section>
<p>请播放完整 GIF 检查动作、遮挡和循环。机械预览不代表视觉验收通过。</p></main>"""
    (output_dir / "index.html").write_text(page, encoding="utf-8")


def preview_scene(config, backend, output_dir, avatars, baseline=None, source=None) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if baseline is not None:
        baseline = Path(baseline)
        if not baseline.is_file():
            raise FileNotFoundError(f"返工场景缺少保存的旧 GIF：{baseline}")
        kind = "rework"
        before_source = baseline
    else:
        if source is None or not Path(source).is_file():
            raise FileNotFoundError("新场景需要未合成源 GIF；返工场景需要保存的旧 GIF")
        kind = "original"
        before_source = Path(source)
    before = output_dir / "before.gif"
    shutil.copyfile(before_source, before)
    result = backend.get_meme(config["key"])(images=list(avatars))
    after = output_dir / "after.gif"
    after.write_bytes(result.getvalue())
    reference = reference_position(config)
    write_triptych(before, output_dir / "before.jpg", reference)
    write_triptych(after, output_dir / "after.jpg", reference)
    write_html(output_dir, kind)
    metadata = {
        "mode": config["mode"],
        "kind": kind,
        "reference_index": config["reference_index"],
        "before": before.name,
        "after": after.name,
        "before_sha256": sha256(before),
        "after_sha256": sha256(after),
        "visual_approval_required": True,
    }
    (output_dir / "preview.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("avatars", nargs="+", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    import meme_generator

    config = json.loads(args.config.read_text(encoding="utf-8"))
    avatars = [path.read_bytes() for path in args.avatars]
    metadata = preview_scene(
        config,
        meme_generator,
        args.output_dir,
        avatars,
        baseline=args.baseline,
        source=args.source,
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
