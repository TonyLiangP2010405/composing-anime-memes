# 验收契约：换头模板

分四关，逐关留证据，数量分开报，**不得合并成“全部完成”**。

## 第一关：机械验证

```bash
/tmp/meme-venv/bin/python - <<'PY'
from pathlib import Path
from meme_generator import get_meme, load_memes
load_memes(Path("/path/to/template/root"))
meme = get_meme("your_key")
print(meme.params_type)
PY
```

检查：

- 模板能被 `load_memes` 加载，`get_meme(key)` 返回 `min_images=1, max_images=1`；
- `meta.json` 存在，含 `key`、`source`、`face_box`、`avatar_size`、`centers`；
- 输出帧数 = 原 GIF 帧数（或说明合并了相同帧）；
- 输出尺寸与原图一致；时长 > 0；
- `avatar_size` ≥ `sqrt(face_w² + face_h²) + 3`（圆形）；椭圆蒙版参数合法，且记录 `ellipse_size`；
- `centers` 数量 = 原帧数，或明确说明是固定中心。

## 第二关：覆盖与对齐

```bash
python scripts/check_coverage.py --meta meta.json --frame 0 --out /tmp/coverage.png

# 或手传参数
python scripts/check_coverage.py --file images/base.gif \
  --box 80,22,100,110 --size 156 --center 130,77 --out /tmp/coverage.png
```

检查：

- 圆形：脸框四角都在头像圆内，输出 `COVERED`；
- 椭圆：只检查内切 70% 脸框，输出 `COVERED (ELLIPSE)`；椭圆四角是耳朵/背景，必须视觉确认旧五官不露；要连四角都盖住就改用大圆；
- `avatar_size` ≥ D_min + 3–5 px（例如 D_min 148.7 → 154–158）；
- 原脸的眼睛、鼻子、嘴、脸颊、下巴、额头没有残边；
- 头像中心在脸上，不在耳朵/身体/道具上；
- 头像没有盖住菜刀、蛋、字幕、问号等原图信息（除非用户要求）；
- 动图至少检查首/中/尾 + 位移最大的一帧，每帧都 `COVERED` / `COVERED (ELLIPSE)`。

**只看首帧不算通过。**

## 第三关：动态跟随

- 动图有 `HEAD_CENTERS`，每帧按对应中心贴；
- 原图的头移动时，头像跟着移动，不漂移、不残影；
- 生成原图/换头并排 GIF：左原图、右换头；关键帧对比图覆盖首/中/尾；
- 缩小到聊天窗口约 200 px 再看一眼，确认没有“贴纸感”。

## 第四关：原图可读性

```bash
python scripts/audit_meme.py --meta meta.json --strict
```

检查：

- `audit_meme.py --strict` 必须 `OK`（不是 `WARN`）；
- 底图题材是 panda/huaji，不是 dog/object；
- 椭圆 ≤ 1.12 × 检测框；头像椭圆面积 ≤ 80% 画面；
- 三层可见性：角色轮廓（耳朵/头套/身体）、梗道具（柠檬/手/刀/花/牌子）、字幕，至少保留两类；
- 缩到 200 px 还能认出原梗；只剩一张头像 = 失败。

任何一项失败，模板淘汰或换底图，不计入通过数。

## 第五关：用户终审

- 给用户看完整预览和原图/换头对比 GIF；
- 用户提出问题的模板记为待修，**不计入通过数**；
- 任何重新渲染（改尺寸、改中心、换底图、改编码）都会让旧初审失效，必须重跑第一、二、三关；
- 终审通过后记录 key、输出文件 SHA-256、底图 `source_sha256`。

## 报告格式

```text
机械验证：通过 X/Y（模板加载、帧数/尺寸/时长、meta.json 完整）
覆盖检查：通过 X/Y（脸框在头像圆内 / 椭圆内切 70% 脸框）
动态跟随：通过 X/Y（逐帧中心与头像位置一致）
原图可读性：通过 X/Y（audit_meme.py + 三层可见性 + 200 px 测试）
视觉初审：通过 X/Y，证据路径…
用户终审：通过 X/Y
待修/淘汰：key + 原因
```

没有任何记录时写“未核验”，不要写 0/100、估算值或计划数。
