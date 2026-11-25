# composing-anime-memes

给 [meme-generator](https://github.com/MemeCrafters/meme-generator) **0.1.x** 做**真·斗图换头模板**的 Agent Skill：从真实斗图表情包（**优先滑稽脸、熊猫脸**，其次狗头/蘑菇头、真人反应图）出发，量脸框、定头像尺寸、逐帧跟随、生成模板、做覆盖/对齐验收。

这个 skill 替代了旧版“圆形/方形开口”流程。旧流程只处理原图里画好的几何开口；新版处理**直接盖脸**的斗图换头，重点解决三类被用户否掉的问题：

- 把内置模板改个名字冒充新模板；
- 自己画插画，不像斗图；
- 动图里头像固定不动，或者头像太小/偏了，原脸露出来。

## 目录

```text
SKILL.md                            # 主流程：三条硬规则、量脸、尺寸、模板契约、验收、红旗
references/head-swap-patterns.md    # 脸框测量、覆盖数学、椭圆蒙版、逐帧跟随
references/source-selection.md      # 找真实斗图底图（发表情/斗图啦/360）与筛选标准
references/acceptance-contract.md   # 机械验证 / 覆盖检查 / 动态跟随 / 视觉初审 / 用户终审
scripts/harvest_fabiaoqing.py       # 发表情搜索页抓取：list → thumbs → large
scripts/track_heads.py              # 光流跟踪 GIF 里的脸中心，输出 HEAD_CENTERS + 可视化
scripts/check_coverage.py           # 画脸框和头像圆，检查是否完整覆盖
templates/head_swap_template/       # 模板骨架：__init__.py.tmpl + _common.py + meta.json.tmpl
```

## 快速使用

```bash
# 1. 找真实斗图底图
python scripts/harvest_fabiaoqing.py list --out /tmp/fbq --pages 4 \
  --keywords 滑稽 滑稽脸 熊猫头 狗头 蘑菇头 拿刀熊猫 拍桌熊猫 滚蛋熊猫
python scripts/harvest_fabiaoqing.py thumbs --out /tmp/fbq
python scripts/harvest_fabiaoqing.py large --out /tmp/fbq --pick 0 2 3

# 2. 量首帧脸框后，跟踪逐帧中心
python scripts/track_heads.py --file /tmp/fbq/large/000.gif --box 80,22,100,110 --out /tmp/track

# 3. 检查覆盖（脸框是否完整落在头像圆里）
python scripts/check_coverage.py --meta /path/to/template/meta.json --frame 0
# 或手传：--file ... --box 80,22,100,110 --size 156 --center 130,77

# 4. 复制 templates/head_swap_template，填 key / 中心 / 尺寸，生成并做原图-换头对比
```

## 核心规则

- 底图必须是真实斗图，不是内置模板、不是插画、不是空白素材。
- 题材优先级：**滑稽脸 → 熊猫脸 → 狗头/蘑菇头 → 真人反应图**。滑稽脸/熊猫脸边界干净、面积大，换头最容易对齐。
- 脸框不是头框：中心按脸框，不按耳朵/身体。
- 圆形直径 ≥ 脸框对角线 + 3–5 px；要保留熊猫耳朵就换椭圆蒙版，但椭圆只保证盖脸型中央，四角是耳朵/背景，必须视觉确认旧五官不露。
- 动图用 `HEAD_CENTERS` 逐帧贴，不能固定一个坐标。
- 覆盖、对齐、跟随、原图信息保留分别验收；机械通过不等于视觉合格。
- 没有验收记录写“未核验”，不写 0 或估算值。

## License

仅供个人/群内非商业使用；素材版权归原作者。
