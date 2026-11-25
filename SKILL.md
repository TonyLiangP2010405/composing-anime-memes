---
name: composing-anime-memes
description: Use when building meme-generator 0.1.x head-swap templates from real 斗图 GIFs or 表情包 (滑稽脸、熊猫头、狗头、蘑菇头、拿刀/拍桌/滚蛋), when the avatar must fully cover the original face, when animated GIF heads move and the avatar must follow per frame, or when the result looks like a pasted sticker / leaves the old face, cheeks, chin, or ears visible.
---

# Composing Anime Memes

## Overview

给 `meme-generator 0.1.x` 做**真·斗图换头模板**：底图必须是真实斗图表情包（滑稽脸、熊猫头、狗头、蘑菇头、拿刀/拍桌/滚蛋等；**不用真人照片/真人反应图**），只替换原图的脸，身体、道具、字幕、边框全部保留。

三条硬规则：

1. **底图必须是真斗图**。不能把 `meme-generator` 内置模板改个名字，不能自己画插画，不能用素材站的空白模板。
2. **头像必须完整盖住原脸**。按脸框（不是整个头/耳朵）对齐；圆形直径至少覆盖脸框对角线，否则脸颊、下巴、额头会露出来。
3. **动图必须逐帧跟随**。原 GIF 的头会动时，模板要存 `HEAD_CENTERS`，每帧按对应中心贴头像；固定一个坐标一定会脱节。

没有通过覆盖/对齐检查、完整 GIF 初审和用户终审的成果，不得标记完成。

## Required workflow

- [ ] 选真实斗图底图：**优先滑稽脸、熊猫脸**，其次狗头/蘑菇头；**不用真人照片/真人反应图**；记录来源 URL 和版权说明。
- [ ] 量脸框：用光流（熊猫头/滑稽脸这种风格化脸）得到每帧脸中心；不要用整个头/耳朵的中心。
- [ ] 定头像尺寸：圆形直径 ≥ 脸框对角线 `sqrt(w²+h²)`；想保留熊猫耳朵就用椭圆蒙版，按脸型而不是正圆。
- [ ] 写模板包：`__init__.py` + `_common.py` + `images/base.gif` + `meta.json`；用 0.1.x 的 `add_meme`。
- [ ] 用真实头像生成；检查帧数、尺寸、时长；生成原图/换头对比 GIF 和关键帧对比图。
- [ ] 逐帧检查：原脸（眼睛、鼻子、嘴、脸颊、下巴、额头）是否完全被盖住；头像是否跟着原图的头动；身体/道具/字幕是否保留。
- [ ] 跑 `scripts/check_coverage.py --meta meta.json` 和 `scripts/track_heads.py`，把覆盖与跟随结果写进交付记录。
- [ ] 记录素材来源、版权、验证证据路径。

## 1. 量脸框与逐帧中心

### 1.1 脸框不是头框

- 熊猫头的耳朵、身体不能作为中心；脸框是白色脸/人脸的矩形。
- **真人底图一律淘汰**：不做真人照片/真人反应图，也不要拿 Haar 硬做；拿到真人素材直接换。
- 熊猫头/风格化脸：先用网格图或肉眼给出首帧脸框，再用 `scripts/track_heads.py` 做光流跟踪，输出每帧中心。
- 不要用模板匹配直接追整张脸：熊猫脸的表情/颜色会变，匹配会跳到耳朵/身体上；光流跟眼睛/鼻子/嘴的特征点更稳。

### 1.2 头像尺寸

圆形要覆盖矩形脸框的四个角，直径至少 `sqrt(w²+h²)`。**理论值再加 3–5 px 余量**：150 对 148.7 只剩 0.67 px，光流抖动 1–2 px 就会露边，建议 154–158（示例 156）。例：

- 脸框 100×110 → D_min 148.7；用 154–158（示例用 156）。
- 脸框 110×110 → D_min 155.6；用 160–162。
- 脸框 90×100 → D_min 134.5；用 138–142。
- 熊猫头特写 600×584 → 用 600。

如果盖脸会盖掉熊猫耳朵，这是取舍：

- 用户要“把脸盖住”时，优先大圆盖脸。
- 用户要保留耳朵时，用椭圆蒙版：椭圆宽高 = 脸框宽高 × 1.05–1.1，中心 = 脸中心；耳朵在椭圆外，自然保留。
- 椭圆蒙版只保证盖住脸型中央，**不保证矩形四角**。要连四角（脸颊/下巴/额头）都盖住，椭圆需 ≥ √2 ≈ 1.42× 脸框，会盖住耳朵——这时直接用大圆。`check_coverage.py --shape ellipse` 只检查内切 70% 脸框，输出 `COVERED (ELLIPSE)`，必须配合视觉初审。

### 1.3 动图

- 先判断头是否动：抽首/中/尾帧，看脸中心位移 > 3 px 就逐帧。
- 用 `scripts/track_heads.py --file base.gif --box x,y,w,h` 输出 `HEAD_CENTERS` 和可视化。
- 把中心写进模板常量；运行时不要依赖 OpenCV（模板只依赖 PIL/pil_utils）。
- 如果头还有明显旋转/缩放，补旋转/缩放参数；只做平移会看起来“贴着脸滑”。

## 2. 模板包契约

```text
<repo>/<key>/
├── __init__.py
├── _common.py
├── meta.json
└── images/base.gif
```

`__init__.py`：

```python
from pathlib import Path

from arclet.alconna import store_true
from pydantic import Field

from meme_generator import (
    MemeArgsModel,
    MemeArgsType,
    ParserOption,
    add_meme,
    get_meme_keys,
)

import importlib.util

_COMMON_SPEC = importlib.util.spec_from_file_location(
    f"{__name__}._common", Path(__file__).parent / "_common.py"
)
_common = importlib.util.module_from_spec(_COMMON_SPEC)
_COMMON_SPEC.loader.exec_module(_common)
avatar = _common.avatar
load_frames = _common.load_frames
paste_center = _common.paste_center
save = _common.save

img_dir = Path(__file__).parent / "images"
HEAD_CENTERS = [(130, 72), (133, 76)]  # 逐帧脸中心，由 track_heads.py 生成


class Model(MemeArgsModel):
    circle: bool = Field(True, description="是否把头像裁成圆形")


args_type = MemeArgsType(
    args_model=Model,
    args_examples=[Model(circle=True), Model(circle=False)],
    parser_options=[
        ParserOption(
            names=["--circle", "圆"],
            default=True,
            action=store_true,
            help_text="是否把头像裁成圆形",
        )
    ],
)


def render(images, texts, args: Model):
    head = avatar(images, 156, shape="circle" if args.circle else "rect")
    source = load_frames(img_dir / "base.gif")
    center_list = [HEAD_CENTERS] if isinstance(HEAD_CENTERS, tuple) else HEAD_CENTERS
    if len(center_list) == 1:
        centers = center_list * len(source)
    elif len(center_list) == len(source):
        centers = center_list
    else:
        raise ValueError(f"{len(source)} frames vs {len(center_list)} centers")
    frames = []
    for index, frame in enumerate(source):
        frame = frame.copy()
        paste_center(frame, head, centers[index])
        frames.append(frame)
    return save(frames, 0.08)


if "key" not in get_meme_keys():
    add_meme(
        "key",
        render,
        min_images=1,
        max_images=1,
        args_type=args_type,
        keywords=["关键词"],
    )
```

- `meta.json` 记录 `key`、`source`、`face_box`、`avatar_size`、`centers`、`source_url`、`license_note`；`scripts/check_coverage.py --meta meta.json` 直接读它。
- `_common.py` 提供 `load_frames`、`avatar`、`paste_center`、`text_img`、`animate_static`、`save`；每个模板目录自带一份，保证单独拷走也能用。
- **不要写 `from ._common import ...`**：`load_memes()` 用 `pkgutil` 直接执行模块，不会把模板目录注册成包，相对 import 会报 `ModuleNotFoundError`。用上面的 `importlib.util.spec_from_file_location` 显式加载同目录 `_common.py`。
- `add_meme` 用 0.1.x 签名；`load_memes` 可能重复执行同一个模板目录，用 `get_meme_keys()` 去重。
- 0.2.x 是 Rust 绑定，API 不同（`Meme.generate`、`Image`、`meme.info.params`），不要混用。

## 3. 生成与验收

```bash
uv venv --python 3.11 /tmp/meme-venv
uv pip install --python /tmp/meme-venv/bin/python "meme-generator==0.1.14" opencv-python-headless
/tmp/meme-venv/bin/python /path/to/_run_test.py
```

至少检查：

- 模板能 `load_memes` 加载，`get_meme(key)` 返回 1 张图的参数。
- 输出帧数 = 原 GIF 帧数（或说明合并了相同帧）；尺寸/时长正常。
- 原图/换头对比 GIF：左原图、右换头；关键帧对比图覆盖首/中/尾。
- 每帧原脸都被盖住：眼睛、鼻子、嘴、脸颊、下巴、额头没有残边。
- 动图头像跟着原图的头走，不是固定坐标。
- 原图的菜刀、蛋、字幕、问号、身体没有被头像盖掉（除非用户要求）。
- 记录 `MECHANICAL_ONLY` 和视觉初审的数量，不合并成“全部完成”。

## 4. 找真实斗图底图

- 主力：发表情 `fabiaoqing.com` 站内搜索（`scripts/harvest_fabiaoqing.py`），或斗图啦 `doutula.com/search?keyword=...`。
- **优先题材：滑稽脸 → 熊猫脸 → 狗头/蘑菇头。真人照片/真人反应图一律不用。** 滑稽脸是规整的黄色圆脸，脸里没有头发、耳朵、手，边界最干净；熊猫脸是白色蛋形脸，黑耳朵/黑身体天然当边框，椭圆蒙版最容易贴准。真人脸型不规整，头发、下巴、手都容易露，还有肖像/版权风险。
- 滑稽脸关键词：`滑稽`、`滑稽脸`、`贴吧滑稽`、`滑稽 动图`；熊猫头关键词见下。
- 关键词按梗分：`滑稽`、`滑稽脸`、`熊猫头 表情包`、`狗头 表情包`、`蘑菇头 表情包`、`拿刀 熊猫`、`拍桌 熊猫`、`滚蛋 熊猫`、`贴脸 表情包`。
- 不要用：`meme-generator` 内置模板、素材站的空白模板、自己画的插画。
- 记录原始页面 URL、图片 URL、SHA-256 到 `meta.json` / `ASSET_SOURCES.md`；素材版权归原作者，仅限群内非商业使用。

## Rationalizations

| 借口 | 现实 |
|---|---|
| “把内置模板改个名字就是新模板” | 用户明确否掉；必须是新底图/新构图 |
| “自己画一个卡通场景也算表情包” | 用户要的是斗图；插画不像斗图 |
| “头像固定一个坐标就行” | 动图的头会动，固定坐标会脱节 |
| “按整个头/耳朵的中心贴” | 脸会偏；按脸框中心 |
| “头像直径等于脸宽就够了” | 脸框四角会露；用对角线 |
| “把熊猫耳朵也盖住才干净” | 耳朵是熊猫识别点；要保留就换椭圆蒙版 |
| “只看首帧就行” | 后续帧会漂移/露脸；逐帧看 |
| “0.2.x 更新，直接用” | API 不兼容；0.1.x |
| “能出图就算完成” | 覆盖、对齐、跟随都要单独验收 |
| “真人反应图更真实，做几张真人” | 一律不用真人底图：肖像/版权风险，脸型也不规整 |
| “素材网上随便找，不用记来源” | 记录来源和版权；非商业使用 |

## Red flags — STOP

- 内置模板改名 / 自己画插画 / 空白模板素材。
- 用真人照片、真人反应图做底图。
- 原脸的眼睛、鼻子、嘴、脸颊、下巴、额头还露着。
- 头像中心在耳朵/身体上，不在脸上。
- 动图里头像固定在原地，原头已经移走。
- 只检查首帧或缩略图。
- 用 0.2.x API 或 `Meme.generate`。
- 没有原图/换头对比证据。
- 头像盖住菜刀、蛋、字幕、问号等原图信息。
- 未通过项计入完成数。

## Delivery contract

```text
机械验证：通过 X/Y（模板加载、帧数/尺寸/时长、meta.json 完整）
覆盖检查：通过 X/Y（脸框在头像圆内 / 椭圆蒙版覆盖）
动态跟随：通过 X/Y（逐帧中心与头像位置一致）
视觉初审：通过 X/Y，证据路径…
用户终审：通过 X/Y
待修/淘汰：key + 原因
```

没有记录写“未核验”，不写 0/100 或估算值。
